// The tools claude-paint added since our first cut, as our server serves them (tools/upstream: run after each sync).
//   node test/upstream.ts <studio>     (a studio with the painter's easel; test/tools.ts's leaves one fit for it)
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const studio = process.argv[2];
const client = new Client({ name: "upstream-test", version: "0" });
const replies = join(studio, "..", `${studio.split("/").pop()}-replies-upstream.jsonl`);
await client.connect(new StdioClientTransport({ command: "node", args: [new URL("../src/server.ts", import.meta.url).pathname, studio, replies] }));
let failed = 0;
async function check(what: string, name: string, args: any, ok: (text: string, err: boolean, images: number) => boolean) {
	const r: any = await client.callTool({ name, arguments: args });
	const text = r.content.filter((c: any) => c.type === "text").map((c: any) => c.text).join(" ");
	const images = r.content.filter((c: any) => c.type === "image").length;
	const pass = ok(text, !!r.isError, images);
	if (!pass) failed++;
	console.log(`${pass ? "ok  " : "FAIL"} ${what}: ${images ? `[${images} image${images > 1 ? "s" : ""}] ` : ""}${text.slice(0, 110).replace(/\n/g, " | ")}`);
	return text;
}
const pile = 'p = pile{{"lead white", 3}, {"yellow ochre", 1}}';
const tools = (await client.listTools()).tools;
const look = tools.find((t) => t.name === "look")!;
const props = Object.keys((look.inputSchema as any).properties ?? {}).sort().join(",");
console.log(props === "at,compare,crop,grid,hold,light,mode,palette,scratch,size,survey" ? "ok   look's options" : `FAIL look's options: ${props}`);

await check("paint tells the painting's clock", "paint", { lua: `${pile}\nb = brush("flat", 12)\nb:load(p, 0.8)\nb:stroke({{100, 100}, {600, 300}})` },
	(t, e) => !e && /day \d+, \d\d:\d\d/.test(t) && t.trim().endsWith("ok"));
await check("the scratch canvas", "paint", { lua: `${pile}\nb = brush("round", 6)\nb:load(p, 0.6)\nb:stroke({{50, 50}, {300, 200}})`, scratch: true },
	(t, e) => !e && t.startsWith("[scratch canvas]"));
await check("new_scratch needs scratch", "paint", { lua: "x = 1", new_scratch: true }, (t, e) => e && t.includes("new_scratch goes with scratch"));
await check("a fresh scratch canvas, no path named", "paint", { lua: "y = 1", scratch: true, new_scratch: true },
	(t, e) => !e && t.startsWith("[scratch canvas]") && !t.includes("paintings/") && t.includes("put aside"));
await check("status of the scratch canvas", "status", { scratch: true }, (t, e) => !e && t.startsWith("[scratch canvas]"));
await check("the scratch canvas's log", "log", { scratch: true }, (t, e) => !e && t.startsWith("[scratch canvas]"));
await check("the painting's log names no box", "log", {}, (t, e) => !e && !t.includes("--@ box") && t.includes("--@ chunk"));
await check("look in a raking light", "look", { mode: "relief", light: "135,25" }, (t, e, n) => !e && n === 1);
await check("look in the gallery light", "look", { mode: "gallery" }, (t, e, n) => !e && n === 1);
const first = await check("look at the scratch canvas", "look", { scratch: true }, (t, e, n) => !e && n === 1 && t.startsWith("[scratch canvas]"));
await check("the palette board", "look", { palette: true }, (t, e, n) => !e && n === 1);
await check("a survey in tiles", "look", { survey: true }, (t, e, n) => !e && n >= 1 && !/budget/i.test(t));
const earlier = /(\S+\.png)/.exec(first)?.[1];
await check("compare with an earlier look", "look", { compare: earlier }, (t, e, n) => !e && n === 1);
await check("compare outside the studio refused", "look", { compare: "/etc/hosts" }, (t, e) => e);
await check("survey and compare together refused", "look", { survey: true, compare: earlier }, (t, e) => e);
await check("the knife held up", "look", { hold: "p", at: "300,200" }, (t, e, n) => (!e && n === 1) || (e && /knife|pile/.test(t)));
await client.close();
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
