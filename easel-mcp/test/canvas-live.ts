// The given canvas through the real server and easel:  node easel-mcp/test/canvas-live.ts <studio with bin/canvas, no painting yet>
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const studio = process.argv[2];
const client = new Client({ name: "canvas-live", version: "0" });
await client.connect(new StdioClientTransport({ command: "node", args: [new URL("../src/server.ts", import.meta.url).pathname, studio] }));
let failed = 0;
async function check(what: string, name: string, args: any, ok: (text: string, err: boolean) => boolean) {
	const r: any = await client.callTool({ name, arguments: args });
	const text = r.content.map((c: any) => c.text ?? `[${c.type}]`).join(" ");
	const pass = ok(text, !!r.isError);
	if (!pass) failed++;
	console.log(`${pass ? "ok  " : "FAIL"} ${what}: ${text.slice(0, 160).replace(/\n/g, " | ")}`);
}
const ground = 'linen=18, seed=7, ground={{pile={{"lead white", 3}, {"yellow ochre", 1}}, um=60, apply="knife", texture=0.3}}';
await check("another shape is refused", "paint", { lua: `canvas{size=300, aspect=1.25, ${ground}}` }, (t, e) => e && t.includes("16:9") && t.includes("aspect=1.7778"));
await check("... and nothing was set up", "status", {}, (t) => !/aspect=1\.25/.test(t));
await check("the scratch canvas is free", "paint", { scratch: true, lua: `canvas{size=100, aspect=1, ${ground}}` }, (t, e) => !e || !t.includes("16:9"));
await check("the given shape is taken", "paint", { lua: `canvas{size=300, aspect=16/9, ${ground}}` }, (t, e) => !e && t.includes("ok"));
await check("the painting has it", "status", {}, (t) => /aspect=1\.77/.test(t));
await check("painting goes on as ever", "paint", { lua: 'p = pile{{"Prussian blue", 1}, {"lead white", 4}}\nwork(rect(100, 100, 300, 200), {hand="body", pile=p, coverage=1})' }, (t, e) => !e);
await client.close();
console.log(failed ? "FAILED" : "all ok");
process.exit(failed ? 1 : 0);
