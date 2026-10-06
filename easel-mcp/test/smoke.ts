// Smoke test: start the server on a studio, paint a small canvas, look, note, status, log, read.
//   node test/smoke.ts <studio>
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const studio = process.argv[2];
const client = new Client({ name: "smoke", version: "0" });
await client.connect(new StdioClientTransport({ command: "node", args: [new URL("../src/server.ts", import.meta.url).pathname, studio] }));
const tools = await client.listTools();
console.log("tools:", tools.tools.map((t) => t.name).join(", "));
const show = (name: string, r: any) => console.log(`-- ${name}${r.isError ? " (error)" : ""}:`,
	r.content.map((c: any) => c.type === "image" ? `[image ${c.mimeType} ${Math.round(c.data.length * 0.75 / 1024)} KB]` : c.text.slice(0, 300)).join(" | "));
const call = async (name: string, args: any = {}) => show(name, await client.callTool({ name, arguments: args }));
await call("paint", { lua: 'canvas{size=300, aspect=1.25, linen=18, seed=7, ground={{pile={{"lead white", 3}, {"yellow ochre", 1}}, um=60, apply="knife", texture=0.3}}}' });
await call("paint", { lua: 'p = pile{{"Prussian blue", 1}, {"lead white", 4}}\nwork(rect(100, 100, 600, 300), {hand="body", pile=p, coverage=1.5})\nprint(wait(30))' });
await call("paint", { lua: "this is not lua" });
await call("look");
await call("look", { crop: "100,100,400,300" });
await call("note", { text: "a first band of blue" });
await call("status");
await call("log");
await call("read", { path: "journal" });
await call("read", { path: "../../../etc/hosts" });
await client.close();
