// The atelier's additions to the easel tools (requirements RUN-3), against a scratch studio.
//   node test/tools.ts <studio>     (a studio made by the runner or spike/run_sitting.py, with no painting yet)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const studio = process.argv[2];
symlinkSync("/etc", join(studio, "notes", "escape"));
writeFileSync(join(studio, "notes", "blob.dat"), Buffer.from([1, 2, 0, 3]));
const client = new Client({ name: "tools-test", version: "0" });
await client.connect(new StdioClientTransport({ command: "node", args: [new URL("../src/server.ts", import.meta.url).pathname, studio] }));
let failed = 0;
async function check(what: string, name: string, args: any, ok: (text: string, err: boolean) => boolean) {
	const r: any = await client.callTool({ name, arguments: args });
	const text = r.content.map((c: any) => c.text ?? `[${c.type}]`).join(" ");
	const pass = ok(text, !!r.isError);
	if (!pass) failed++;
	console.log(`${pass ? "ok  " : "FAIL"} ${what}: ${text.slice(0, 120).replace(/\n/g, " | ")}`);
}
const names = (await client.listTools()).tools.map((t) => t.name).sort().join(",");
console.log(names === "edit,log,look,note,paint,read,status,write" ? "ok   tools" : `FAIL tools: ${names}`);
await check("studio listing hides bin/", "read", { path: "." }, (t, e) => !e && t.includes("notes/") && !t.includes("bin") && !t.includes("out"));
await check("bin/ refused", "read", { path: "bin/easel" }, (t, e) => e && t.includes("outside the studio"));
await check("bin/ listing refused", "read", { path: "bin" }, (t, e) => e);
await check("out/ refused", "read", { path: "out/easel/painting/server.log" }, (t, e) => e);
await check("../ refused", "read", { path: "../" }, (t, e) => e);
await check("absolute path refused", "read", { path: "/etc/hosts" }, (t, e) => e);
await check("link out refused", "read", { path: "notes/escape/hosts" }, (t, e) => e);
await check("binary refused", "read", { path: "notes/blob.dat" }, (t, e) => e && t.includes("isn't text"));
await check("folder listing", "read", { path: "notes" }, (t, e) => !e && t.includes("easel_guide.md") && t.includes("research/"));
await check("long file is capped", "read", { path: "notes/easel_guide.md" }, (t, e) => !e && t.length <= 61_000);
await check("write notebook", "write", { path: "notebook.md", text: "first line\nsecond line\n" }, (t, e) => !e);
await check("edit notebook", "edit", { path: "notebook.md", replaces: "second", text: "2nd" }, (t, e) => !e);
await check("notebook reads back", "read", { path: "notebook.md" }, (t, e) => t.includes("2nd line"));
await check("write elsewhere refused", "write", { path: "BRIEF.md", text: "x" }, (t, e) => e);
await check("write via ../ refused", "write", { path: "../notebook.md", text: "x" }, (t, e) => e);
await check("edit missing passage", "edit", { path: "notebook.md", replaces: "nope", text: "x" }, (t, e) => e);
await check("paint needs lua or file", "paint", {}, (t, e) => e);
await check("paint file must be toolkit", "paint", { file: "BRIEF.md" }, (t, e) => e);
await check("canvas", "paint", { lua: 'canvas{size=300, aspect=1.25, linen=18, seed=7, ground={{pile={{"lead white", 3}}, um=60, apply="knife", texture=0.3}}}' }, (t, e) => !e);
await check("write toolkit", "write", { path: "toolkit.lua", text: "function dab(x, y) print('dab', x, y) end\n" }, (t, e) => !e);
await check("paint toolkit", "paint", { file: "toolkit.lua" }, (t, e) => !e && t.endsWith("ok"));
await check("toolkit defined globals", "paint", { lua: "dab(1, 2)" }, (t, e) => !e && t.includes("dab"));
await check("toolkit is in the log", "log", {}, (t, e) => t.includes("function dab"));
await client.close();
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
