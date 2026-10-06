/**
 * The easel as an MCP server, for an artist working in Claude Code.
 *
 * The tools and their descriptions are claude-paint's painter tools (harness/painter/easel-tools.ts,
 * by Alice, MIT), served over MCP instead of as pi tools. The easel client and journal revision are
 * claude-paint's own files, unchanged, in ./upstream.
 *
 *   node src/server.ts <studio>
 *
 * The studio is the artist's folder, named as a painter would name things: brief, notebook, toolkit,
 * journal, easel guide, notes on oil paint, walls/ (and, out of its reach, bin/easel, paintings/, out/).
 * Added to claude-paint's tools (requirements RUN-3): `read` lists folders and refuses bin/, paintings/
 * and anything that isn't text or an image; `write` and `edit` change only the notebook and the toolkit,
 * keeping every change; `paint` can run the toolkit as its chunk; `log` pages through the painting's log.
 * Nothing here counts the artist's work or times the machine (see upstream/easel-client.ts).
 */
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, statSync, writeFileSync } from "node:fs";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
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
// the runner's audit compares every tool result in the transcript with what this server sent (requirements NFR-10):
// each reply's text goes to a log outside the studio, given as the second argument
const replyLog = process.argv[3];
function sent(r: { content: Content[]; isError?: boolean }) {
	if (replyLog) {
		const text = r.content.filter((c) => c.type === "text").map((c) => (c as { text: string }).text);
		appendFileSync(replyLog, JSON.stringify({ text, error: !!r.isError }) + "\n");
	}
	return r;
}
const say = (t: string) => sent({ content: [{ type: "text", text: t }] as Content[] });
const fail = (t: string) => sent({ content: [{ type: "text", text: t }] as Content[], isError: true });

/** One tool call at a time: the easel is one hand at one canvas (pi ran these with executionMode "sequential"). */
let queue: Promise<unknown> = Promise.resolve();
function serial<A>(fn: (a: A) => Promise<{ content: Content[]; isError?: boolean }>) {
	return (a: A) => {
		const run = queue.then(() => fn(a));
		queue = run.catch(() => undefined);
		return run;
	};
}

/** What a chunk printed, kept under Claude Code's output limit: its end, as a terminal keeps it (requirements Q3). */
const PRINT_MAX = 20_000;
const capped = (t: string) => (t.length <= PRINT_MAX ? t : "(the beginning of what the chunk printed is left out)\n" + t.slice(-PRINT_MAX));

const server = new McpServer({ name: "easel", version: "0.1.0" });

server.registerTool("paint", {
	description:
		"Run a chunk of Lua at the easel (the easel guide). The reply is what the chunk printed, then `ok`. " +
		"A chunk that stops with an error changes nothing.",
	inputSchema: {
		lua: z.string().optional().describe("the chunk"),
		file: z.string().optional().describe("\"toolkit\": run your toolkit as the chunk"),
	},
}, serial(async ({ lua, file }: { lua?: string; file?: string }) => {
	if ((lua === undefined) === (file === undefined)) return fail("paint: give either `lua` or `file`");
	if (file !== undefined) {
		if (file !== TOOLKIT) return fail(`paint: \`file\` can only be ${TOOLKIT}`);
		const path = resolve(studio, TOOLKIT);
		if (!existsSync(path)) return fail(`paint: there is no ${TOOLKIT} yet`);
		lua = readFileSync(path, "utf8"); // it runs, and is logged, as an ordinary chunk
	}
	try {
		return say(capped(paintReply(await atEasel(studio, ["do", "-"], lua!))));
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
	return sent({ content: [{ type: "text", text: said }, { type: "image", data, mimeType: "image/png" }] as Content[] });
}));

server.registerTool("note", {
	description: "Add an entry to your journal, stamped with the painting's time. " +
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
	description: "The painting so far: every chunk that ran, in order. With offset (the first line, from 1) and limit " +
		"(how many lines), that part of it, with line numbers.",
	inputSchema: { offset: z.number().int().optional(), limit: z.number().int().optional() },
}, serial(async (p: { offset?: number; limit?: number }) => {
	try {
		const log = logReply(await atEasel(studio, ["log"], undefined));
		if (p.offset === undefined && p.limit === undefined) return say(tail(log, 50_000, "`log` with an offset shows them"));
		return say(numbered(log, "the log", p.offset, p.limit));
	} catch (e) {
		return fail((e as Error).message);
	}
}));

const IMAGES: Record<string, string> = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };
const MAX_LINES = 2000;
// Claude Code caps an MCP tool's reply (MAX_MCP_OUTPUT_TOKENS) and says so in tokens: stay well under it
const MAX_CHARS = 60_000;
// the easel itself (bin/) and its working files (out/: looks, sockets, a server log with machine times): not
// something the painter reads; it sees the canvas with look (requirements RUN-3, RUN-8, ENG-7)
// paintings/: the easel's record of the painting, which the painter reads with `log` (owner, 2026-10-06: the
// studio names things as a painter would, without file paths)
const HIDDEN = new Set(["bin", "out", "paintings"]);

/** The studio-relative path of a resolved real path ("" for the studio itself). */
// the studio's disk ignores case (APFS): `OUT/` is `out/`, so every comparison here is in lower case (QA Q1)
const inStudio = (real: string) => relative(realpathSync.native(studio), real);
const hidden = (real: string) => {
	const parts = inStudio(real).split(sep);
	return HIDDEN.has(parts[0].toLowerCase()) || parts.some((x) => x.startsWith("."));
};
/** Text, as far as a reader can tell: no NUL byte in the first 8 KB. */
const isText = (buf: Buffer) => !buf.subarray(0, 8192).includes(0);

server.registerTool("read", {
	description: "Read a file in the studio: text with its line numbers (offset: the first line, from 1; limit: how many lines), " +
		"or an image. A folder gives what is in it.",
	inputSchema: { path: z.string(), offset: z.number().int().optional(), limit: z.number().int().optional() },
}, serial(async (p: { path: string; offset?: number; limit?: number }) => {
	const found = studioPath(studio, p.path);
	if (!found || !existsSync(found)) return fail(found ? `${p.path}: no such file in the studio` : `${p.path} is outside the studio`);
	const real = realpathSync.native(found); // the true case of the path
	if (inStudio(real) !== "" && hidden(real)) return fail(`${p.path} is outside the studio`);
	let st;
	try {
		st = statSync(real);
	} catch {
		return fail(`${p.path} can't be read`);
	}
	if (!st.isDirectory() && !st.isFile()) return fail(`${p.path} can't be read`);
	if (st.isDirectory()) {
		const names = readdirSync(real, { withFileTypes: true })
			.filter((d) => !d.name.startsWith(".") && !(inStudio(real) === "" && HIDDEN.has(d.name.toLowerCase())))
			.map((d) => (d.isDirectory() ? `${d.name}/` : d.name))
			.sort();
		return say(names.length ? names.join("\n") : "(empty)");
	}
	const mime = IMAGES[extname(real).toLowerCase()] ?? imageType(real);
	if (mime) return sent({ content: [{ type: "image", data: readFileSync(real).toString("base64"), mimeType: mime }] as Content[] });
	const buf = readFileSync(real);
	if (!isText(buf)) return fail(`${p.path} isn't text or an image`);
	return say(numbered(buf.toString("utf8"), p.path, p.offset, p.limit));
}));

/** Lines of `body` with their numbers, from `offset` (from 1), at most `limit` of them and under MAX_CHARS. */
function numbered(body: string, name: string, offset?: number, limit?: number): string {
	const p = { offset, limit };
	const lines = body.split("\n");
	if ((p.offset ?? 1) > lines.length) return `(${name} ends before line ${p.offset})`;
	const from = Math.max(1, p.offset ?? 1);
	let n = Math.max(1, Math.min(p.limit ?? MAX_LINES, MAX_LINES));
	let shown = lines.slice(from - 1, from - 1 + n).map((l, i) => `${String(from + i).padStart(6)}\t${l}`);
	while (n > 1 && shown.join("\n").length > MAX_CHARS) {
		n = Math.floor(n / 2);
		shown = shown.slice(0, n);
	}
	const more = from - 1 + n < lines.length ? `\n(${lines.length - (from - 1 + n)} more lines; read on with offset ${from + n})` : "";
	const whole = shown.join("\n");
	const cut = whole.length > MAX_CHARS ? `\n(line ${from} goes on past what one read shows)` : "";
	return whole.slice(0, MAX_CHARS) + cut + more;
}

/** An image by its first bytes, for a file named without an extension (the paintings on the walls). */
function imageType(path: string): string | undefined {
	const b = readFileSync(path).subarray(0, 12);
	if (b[0] === 0x89 && b.subarray(1, 4).toString("latin1") === "PNG") return "image/png";
	if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "image/jpeg";
	if (b.subarray(0, 4).toString("latin1") === "RIFF" && b.subarray(8, 12).toString("latin1") === "WEBP") return "image/webp";
	return undefined;
}

/** The painter's own files, which it may write: they stay in the studio from one painting to the next. */
const NOTEBOOK = "notebook";
const TOOLKIT = "toolkit";
const WRITABLE = new Set([NOTEBOOK, TOOLKIT]);
const REVISIONS = "out/easel/write-revisions.jsonl";

/** Keep every change, whole, so the record of what was written first survives (as journal.ts does for the journal). */
function keep(path: string, before: string, after: string) {
	const log = resolve(studio, REVISIONS);
	mkdirSync(dirname(log), { recursive: true });
	appendFileSync(log, JSON.stringify({ at: new Date().toISOString(), path, before, after }) + "\n");
}

function writable(path: string): string | undefined {
	const real = studioPath(studio, path);
	const rel = real && relative(realpathSync.native(studio), real).toLowerCase();
	return rel && WRITABLE.has(rel) ? rel : undefined;
}

/** Replace a file whole or not at all: a kill mid-write never leaves half a notebook. */
function atomicWrite(path: string, text: string) {
	const tmp = `${path}.${process.pid}.tmp`;
	writeFileSync(tmp, text);
	renameSync(tmp, path);
}

server.registerTool("write", {
	description: `Write ${NOTEBOOK} or ${TOOLKIT} in full: \`text\` becomes the whole file.`,
	inputSchema: { path: z.string(), text: z.string() },
}, serial(async (p: { path: string; text: string }) => {
	const rel = writable(p.path);
	if (!rel) return fail(`write: only ${NOTEBOOK} and ${TOOLKIT} can be written`);
	const path = resolve(studio, rel);
	const before = existsSync(path) ? readFileSync(path, "utf8") : "";
	keep(rel, before, p.text);
	atomicWrite(path, p.text);
	return say(`wrote ${rel}`);
}));

server.registerTool("edit", {
	description: `Change one passage of ${NOTEBOOK} or ${TOOLKIT}: give the exact passage as \`replaces\`; \`text\` takes its place.`,
	inputSchema: { path: z.string(), replaces: z.string(), text: z.string() },
}, serial(async (p: { path: string; replaces: string; text: string }) => {
	const rel = writable(p.path);
	if (!rel) return fail(`edit: only ${NOTEBOOK} and ${TOOLKIT} can be changed`);
	const path = resolve(studio, rel);
	if (!existsSync(path)) return fail(`edit: ${rel} is empty; use write`);
	if (!p.replaces) return fail("edit: `replaces` is empty; give the exact passage to change");
	const before = readFileSync(path, "utf8");
	const at = before.indexOf(p.replaces);
	if (at < 0) return fail(`edit: the passage given in \`replaces\` isn't in ${rel} (it has to match exactly)`);
	if (before.indexOf(p.replaces, at + 1) >= 0) return fail(`edit: the passage is in ${rel} more than once; give more of it`);
	const after = before.slice(0, at) + p.text + before.slice(at + p.replaces.length);
	keep(rel, before, after);
	atomicWrite(path, after);
	return say(`changed ${rel}`);
}));

await server.connect(new StdioServerTransport());
