/**
 * The easel as an MCP server, for an artist working in Claude Code.
 *
 * The tools and their descriptions are claude-paint's painter tools (harness/painter/easel-tools.ts,
 * by Alice, MIT), served over MCP instead of as pi tools. The easel client and journal revision are
 * claude-paint's own files, unchanged, in ./upstream.
 *
 *   node src/server.ts <studio>
 *
 * The studio is the artist's folder: bin/easel (the painter build), BRIEF.md, notes/, paintings/.
 * Nothing here counts the artist's work or times the machine (see upstream/easel-client.ts).
 */
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, resolve } from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { reviseJournal } from "./upstream/journal.ts";
import {
	atEasel, hideCounters, logReply, lookArgs, paintReply, renameLook, statusReply, studioPath, tail, toolWords,
} from "./upstream/easel-client.ts";

const studio = resolve(process.argv[2] ?? process.cwd());
if (!existsSync(resolve(studio, "bin", "easel"))) {
	console.error(`easel-mcp: no bin/easel in ${studio}`);
	process.exit(2);
}

type Content = { type: "text"; text: string } | { type: "image"; data: string; mimeType: string };
const say = (t: string) => ({ content: [{ type: "text", text: t }] as Content[] });
const fail = (t: string) => ({ content: [{ type: "text", text: t }] as Content[], isError: true });

/** One tool call at a time: the easel is one hand at one canvas (pi ran these with executionMode "sequential"). */
let queue: Promise<unknown> = Promise.resolve();
function serial<A>(fn: (a: A) => Promise<{ content: Content[]; isError?: boolean }>) {
	return (a: A) => {
		const run = queue.then(() => fn(a));
		queue = run.catch(() => undefined);
		return run;
	};
}

const server = new McpServer({ name: "easel", version: "0.1.0" });

server.registerTool("paint", {
	description:
		"Run a chunk of Lua at the easel (notes/easel_guide.md). The reply is what the chunk printed, then `ok`. " +
		"A chunk that stops with an error changes nothing.",
	inputSchema: { lua: z.string().describe("the chunk") },
}, serial(async ({ lua }: { lua: string }) => {
	try {
		return say(paintReply(await atEasel(studio, ["do", "-"], lua)));
	} catch (e) {
		return fail(hideCounters((e as Error).message));
	}
}));

server.registerTool("look", {
	description:
		"Look at the canvas as it is now. Without options: the whole canvas, scaled down. " +
		"crop: \"x0,y0,x1,y1\" in canvas units (two opposite corners), shown at 1:1 pixels. " +
		"mode: \"value\", \"squint\", \"mirror\" or several, comma-separated. size: the long side in pixels. " +
		"grid: true, or a spacing in canvas units.",
	inputSchema: {
		crop: z.string().optional(),
		mode: z.string().optional(),
		size: z.number().optional(),
		grid: z.union([z.boolean(), z.number()]).optional(),
	},
}, serial(async (p: { crop?: string; mode?: string; size?: number; grid?: boolean | number }) => {
	let said: string;
	try {
		said = await atEasel(studio, ["look", ...lookArgs(p)], undefined);
	} catch (e) {
		return fail(toolWords((e as Error).message)); // the easel's messages name its command-line flags
	}
	let path: string;
	({ said, path } = renameLook(studio, said));
	const data = readFileSync(resolve(studio, path)).toString("base64");
	return { content: [{ type: "text", text: said }, { type: "image", data, mimeType: "image/png" }] as Content[] };
}));

server.registerTool("note", {
	description: "Add an entry to your journal, notes/journal.md, stamped with the painting's time. " +
		"To revise what is already there, give the exact passage to change as `replaces`: `text` takes its place.",
	inputSchema: { text: z.string(), replaces: z.string().optional() },
}, serial(async (p: { text: string; replaces?: string }) => {
	try {
		if (p.replaces !== undefined) return say(reviseJournal(studio, p.replaces, p.text));
		return say(await atEasel(studio, ["note", "-"], p.text));
	} catch (e) {
		return fail((e as Error).message);
	}
}));

server.registerTool("status", {
	description: "The canvas's setup.",
	inputSchema: {},
}, serial(async () => {
	try {
		return say(statusReply(await atEasel(studio, ["status"], undefined)));
	} catch (e) {
		return fail((e as Error).message);
	}
}));

server.registerTool("log", {
	description: "The painting so far: every chunk that ran, in order (paintings/lua/painting.lua).",
	inputSchema: {},
}, serial(async () => {
	try {
		return say(tail(logReply(await atEasel(studio, ["log"], undefined))));
	} catch (e) {
		return fail((e as Error).message);
	}
}));

const IMAGES: Record<string, string> = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };
const MAX_LINES = 2000;

server.registerTool("read", {
	description: "Read a file in the studio: text with its line numbers (offset: the first line, from 1; limit: how many lines), " +
		"or an image.",
	inputSchema: { path: z.string(), offset: z.number().int().optional(), limit: z.number().int().optional() },
}, serial(async (p: { path: string; offset?: number; limit?: number }) => {
	const real = studioPath(studio, p.path);
	if (!real) return fail(`${p.path} is outside the studio`);
	if (!existsSync(real)) return fail(`${p.path}: no such file in the studio`);
	if (statSync(real).isDirectory()) return fail(`${p.path} is a folder`);
	const mime = IMAGES[extname(real).toLowerCase()];
	if (mime) return { content: [{ type: "image", data: readFileSync(real).toString("base64"), mimeType: mime }] as Content[] };
	const lines = readFileSync(real, "utf8").split("\n");
	const from = Math.max(1, p.offset ?? 1);
	const n = Math.max(1, Math.min(p.limit ?? MAX_LINES, MAX_LINES));
	const shown = lines.slice(from - 1, from - 1 + n).map((l, i) => `${String(from + i).padStart(6)}\t${l}`).join("\n");
	const more = from - 1 + n < lines.length ? `\n(${lines.length - (from - 1 + n)} more lines; read on with offset ${from + n})` : "";
	return say(shown + more);
}));

await server.connect(new StdioServerTransport());
