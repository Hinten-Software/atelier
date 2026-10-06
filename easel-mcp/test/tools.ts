// The atelier's additions to the easel tools (requirements RUN-3), against a scratch studio.
//   node test/tools.ts <studio>     (a studio made by the runner or spike/run_sitting.py, with no painting yet)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const studio = process.argv[2];
symlinkSync("/etc", join(studio, "walls", "escape"));
writeFileSync(join(studio, "walls", "blob"), Buffer.from([1, 2, 0, 3]));
// a painting on the walls, named as the runner hangs it: no extension
writeFileSync(join(studio, "walls", "1 Test Study"), Buffer.from("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4c50000000049454e44ae426082", "hex"));
const client = new Client({ name: "tools-test", version: "0" });
const replies = join(studio, "..", `${studio.split("/").pop()}-replies.jsonl`);
await client.connect(new StdioClientTransport({ command: "node", args: [new URL("../src/server.ts", import.meta.url).pathname, studio, replies] }));
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
await check("studio listing hides bin/", "read", { path: "." }, (t, e) => !e && t.includes("easel guide") && t.includes("walls/") && !t.includes("bin") && !t.includes("out") && !t.includes("paintings"));
await check("bin/ refused", "read", { path: "bin/easel" }, (t, e) => e && t.includes("outside the studio"));
await check("bin/ listing refused", "read", { path: "bin" }, (t, e) => e);
await check("out/ refused", "read", { path: "out/easel/painting/server.log" }, (t, e) => e);
await check("../ refused", "read", { path: "../" }, (t, e) => e);
await check("absolute path refused", "read", { path: "/etc/hosts" }, (t, e) => e);
await check("link out refused", "read", { path: "walls/escape/hosts" }, (t, e) => e);
await check("binary refused", "read", { path: "walls/blob" }, (t, e) => e && t.includes("isn't text"));
await check("folder listing", "read", { path: "walls" }, (t, e) => !e && t.includes("1 Test Study"));
await check("a painting on the walls is an image", "read", { path: "walls/1 Test Study" }, (t, e) => !e && t.includes("[image]"));
await check("paintings/ refused", "read", { path: "paintings/lua/painting.lua" }, (t, e) => e);
await check("long file is capped", "read", { path: "easel guide" }, (t, e) => !e && t.length <= 61_000);
await check("write notebook", "write", { path: "notebook", text: "first line\nsecond line\n" }, (t, e) => !e);
await check("edit notebook", "edit", { path: "notebook", replaces: "second", text: "2nd" }, (t, e) => !e);
await check("notebook reads back", "read", { path: "notebook" }, (t, e) => t.includes("2nd line"));
await check("write elsewhere refused", "write", { path: "brief", text: "x" }, (t, e) => e);
await check("write via ../ refused", "write", { path: "../notebook", text: "x" }, (t, e) => e);
await check("edit missing passage", "edit", { path: "notebook", replaces: "nope", text: "x" }, (t, e) => e);
await check("paint needs lua or file", "paint", {}, (t, e) => e);
await check("paint file must be toolkit", "paint", { file: "brief" }, (t, e) => e);
await check("canvas", "paint", { lua: 'canvas{size=300, aspect=1.25, linen=18, seed=7, ground={{pile={{"lead white", 3}}, um=60, apply="knife", texture=0.3}}}' }, (t, e) => !e);
await check("write toolkit", "write", { path: "toolkit", text: "function dab(x, y) print('dab', x, y) end\n" }, (t, e) => !e);
await check("paint toolkit", "paint", { file: "toolkit" }, (t, e) => !e && t.endsWith("ok"));
await check("toolkit defined globals", "paint", { lua: "dab(1, 2)" }, (t, e) => !e && t.includes("dab"));
await check("toolkit is in the log", "log", {}, (t, e) => t.includes("function dab"));
// QA Q1, Q2, Q3, Q16
for (const v of ["OUT", "Out/easel/painting", "OUT/easel/painting/server.log", "BIN", "Bin/easel", "out/easel/painting/lock"])
	await check(`case variant ${v} refused`, "read", { path: v }, (t, e) => e);
await check("log without chunk numbers", "log", {}, (t, e) => !e && t.includes("--@ chunk") && !/--@ chunk \d/.test(t));
await check("log pages with offset", "log", { offset: 1, limit: 3 }, (t, e) => !e && /^\s+1\t/.test(t) && t.includes("more lines"));
await check("NOTEBOOK writes the notebook", "write", { path: "NOTEBOOK", text: "case\n" }, (t, e) => !e);
await check("the notebook has it", "read", { path: "notebook" }, (t, e) => t.includes("case"));
await check("offset past the end", "read", { path: "notebook", offset: 99 }, (t, e) => !e && t.includes("ends before"));
await check("long print is capped", "paint", { lua: 'for i=1,20000 do print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") end' },
	(t, e) => !e && t.length < 21_000 && t.includes("left out"));
await client.close();
const logged = readFileSync(replies, "utf8").trim().split("\n").length;
if (logged < 30) { failed++; console.log(`FAIL reply log has ${logged} entries`); } else console.log("ok   every reply is logged");
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
