// A local preview of the site with working notes, for the owner on the LAN before launch:
//   node deploy/notes/preview.mjs            http://<mac>:8801/
// Serves the export (DATA/site) and runs the real Worker (worker.js) on /api/notes against a local SQLite file
// (DATA/run/notes-preview.sqlite) with the real schema. The bot check is off: the pages get the key "preview"
// and the Worker's call to Turnstile is answered locally. Nothing here is used by the public site.
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, normalize } from "node:path";
import { homedir } from "node:os";
import { DatabaseSync } from "node:sqlite";
import worker from "./worker.js";

const DATA = process.env.ATELIER_DATA || join(homedir(), "atelier-data");
const SITE = join(DATA, "site");
const PORT = Number(process.env.PORT || 8801);
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".txt": "text/plain", ".lua": "text/plain" };

const sqlite = new DatabaseSync(join(DATA, "run", "notes-preview.sqlite"));
sqlite.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8").replace(/CREATE (TABLE|INDEX) (?!IF NOT EXISTS)/g, "CREATE $1 IF NOT EXISTS "));
class Statement {
  constructor(sql, args = []) { this.sql = sql; this.args = args; }
  bind(...args) { return new Statement(this.sql, args); }
  async all() { return { success: true, meta: {}, results: sqlite.prepare(this.sql).all(...this.args).map((r) => ({ ...r })) }; }
  async first(col) { const r = sqlite.prepare(this.sql).get(...this.args); return r ? (col ? r[col] : { ...r }) : null; }
  async run() { const r = sqlite.prepare(this.sql).run(...this.args); return { success: true, meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } }; }
}
const env = { DB: { prepare: (sql) => new Statement(sql) }, TURNSTILE_SECRET: "preview", RATE_SECRET: "preview" };
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) =>
  String(url).startsWith("https://challenges.cloudflare.com/") ? Response.json({ success: true }) : realFetch(url, init);

createServer(async (req, res) => {
  const url = new URL(req.url, "http://preview");
  if (url.pathname.startsWith("/api/notes")) {
    const body = ["GET", "HEAD"].includes(req.method) ? undefined : await new Promise((ok) => { const b = []; req.on("data", (c) => b.push(c)); req.on("end", () => ok(Buffer.concat(b))); });
    const headers = new Headers(Object.entries(req.headers).filter(([, v]) => typeof v === "string"));
    headers.set("CF-Connecting-IP", req.socket.remoteAddress || "127.0.0.1");
    const r = await worker.fetch(new Request(url, { method: req.method, headers, body }), env, { waitUntil() {} });
    res.writeHead(r.status, Object.fromEntries(r.headers));
    res.end(Buffer.from(await r.arrayBuffer()));
    return;
  }
  let path = normalize(join(SITE, decodeURIComponent(url.pathname)));
  if (!path.startsWith(SITE)) { res.writeHead(404); res.end(); return; }
  if (existsSync(path) && statSync(path).isDirectory()) path = join(path, "index.html");
  if (!existsSync(path)) { res.writeHead(404); res.end("not found"); return; }
  let data = readFileSync(path);
  if (extname(path) === ".html") data = Buffer.from(data.toString().replace(/(<meta name="turnstile" content=")[^"]*"/, '$1preview"'));
  res.writeHead(200, { "Content-Type": TYPES[extname(path)] || "application/octet-stream", "Cache-Control": "no-store" });
  res.end(data);
}).listen(PORT, "0.0.0.0", () => console.log(`preview: http://0.0.0.0:${PORT}/ (notes in ${join(DATA, "run", "notes-preview.sqlite")})`));
