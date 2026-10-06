// Visitor notes for notart.fyi — Cloudflare Worker on notart.fyi/api/notes*.
//
// Storage is D1 (binding DB). Bots are kept out with Turnstile. Nothing about
// a visitor is stored: no IP, user agent, country or other header. The rate
// limiter keeps only a daily-rotating HMAC of the IP, with counts.

const PATH = '/api/notes';
const PAGE_SIZE = 50;
const MAX_BODY_BYTES = 4096;
const MAX_TEXT = 500; // code points
const MAX_TOKEN = 2048; // Turnstile's documented maximum
const PER_HOUR = 5;
const PER_DAY = 20;
const WORK_RE = /^[a-z]+-\d{3}$/;
const SITEVERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname !== PATH) return error(404, 'Not found.');
    try {
      if (request.method === 'GET') return await list(url, env);
      if (request.method === 'POST') return await create(request, env, ctx);
      return error(405, 'Method not allowed.', { Allow: 'GET, POST' });
    } catch (err) {
      console.error('notes: unexpected error', err && err.message);
      return error(500, 'Something went wrong. Please try again later.');
    }
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(pruneRate(env, new Date()));
  },
};

// ---------------------------------------------------------------- GET

async function list(url, env) {
  const work = url.searchParams.get('work');
  const before = url.searchParams.get('before');
  if (work !== null && !WORK_RE.test(work)) return error(400, 'Unknown work.');
  if (before !== null && !/^[1-9]\d{0,15}$/.test(before)) return error(400, 'Bad cursor.');

  const where = ['hidden = 0'];
  const args = [];
  if (work !== null) { where.push('work = ?'); args.push(work); }
  if (before !== null) { where.push('id < ?'); args.push(Number(before)); }
  args.push(PAGE_SIZE + 1); // one extra row tells us whether a next page exists

  const { results } = await env.DB
    .prepare(`SELECT id, at, work, text FROM notes WHERE ${where.join(' AND ')} ORDER BY id DESC LIMIT ?`)
    .bind(...args)
    .all();

  const notes = results.slice(0, PAGE_SIZE).map((r) => ({ id: r.id, at: r.at, work: r.work, text: r.text }));
  const next = results.length > PAGE_SIZE ? String(notes[notes.length - 1].id) : null;
  return json(200, { notes, next }, { 'Cache-Control': 'public, max-age=30' });
}

// ---------------------------------------------------------------- POST

async function create(request, env, ctx) {
  const raw = await readLimited(request, MAX_BODY_BYTES);
  if (raw === null) return error(400, 'That note is too long.');

  let body;
  try { body = JSON.parse(raw); } catch { return error(400, 'Could not read the note.'); }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return error(400, 'Could not read the note.');

  if (typeof body.text !== 'string') return error(400, 'Please write something.');
  const text = cleanText(body.text);
  const length = [...text].length;
  if (length === 0) return error(400, 'Please write something.');
  if (length > MAX_TEXT) return error(400, `Notes can be at most ${MAX_TEXT} characters.`);
  if (looksLikeLink(text)) return error(400, 'Links are not allowed.');

  let work = null;
  if (body.work !== undefined && body.work !== null && body.work !== '') {
    if (typeof body.work !== 'string' || !WORK_RE.test(body.work)) return error(400, 'Unknown work.');
    work = body.work;
  }

  const token = body.token;
  if (typeof token !== 'string' || token.length === 0 || token.length > MAX_TOKEN) {
    return error(403, 'Please complete the check first.');
  }

  const now = new Date();
  const day = now.toISOString().slice(0, 10);
  const hour = now.toISOString().slice(0, 13);
  const key = await rateKey(env.RATE_SECRET, day, request.headers.get('CF-Connecting-IP') || '');

  // Check the limit before asking Turnstile, so a limited visitor costs nothing.
  const usage = await env.DB
    .prepare('SELECT COALESCE(SUM(count), 0) AS d, COALESCE(SUM(CASE WHEN hour = ? THEN count END), 0) AS h FROM rate WHERE key = ? AND day = ?')
    .bind(hour, key, day)
    .first();
  if (usage.h >= PER_HOUR || usage.d >= PER_DAY) {
    return error(429, 'You have left a lot of notes. Please wait a while.', { 'Retry-After': '3600' });
  }

  const verdict = await verifyTurnstile(env.TURNSTILE_SECRET, token);
  if (verdict === 'unavailable') return error(503, 'The check is not available right now. Please try again.');
  if (verdict !== 'ok') return error(403, 'The check failed. Please try again.');

  await env.DB
    .prepare('INSERT INTO rate (key, day, hour, count) VALUES (?, ?, ?, 1) ON CONFLICT (key, hour) DO UPDATE SET count = count + 1')
    .bind(key, day, hour)
    .run();

  const at = now.toISOString().slice(0, 16) + 'Z';
  const row = await env.DB
    .prepare('INSERT INTO notes (at, work, text) VALUES (?, ?, ?) RETURNING id')
    .bind(at, work, text)
    .first();

  ctx.waitUntil(pruneRate(env, now));
  return json(201, { id: row.id, at });
}

// ---------------------------------------------------------------- helpers

// Reads at most `limit` bytes of the body; returns null if it is larger.
async function readLimited(request, limit) {
  const declared = Number(request.headers.get('Content-Length'));
  if (declared > limit) return null;
  if (!request.body) return '';
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) { reader.cancel().catch(() => {}); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const c of chunks) { bytes.set(c, offset); offset += c.byteLength; }
  return new TextDecoder().decode(bytes);
}

// Normalises line breaks, drops control characters (keeping \n) and invisible
// characters that could hide a link, caps blank runs, trims.
export function cleanText(input) {
  const s = typeof input.toWellFormed === 'function' ? input.toWellFormed() : input;
  return s
    .normalize('NFC')
    .replace(/\r\n?/g, '\n')
    .replace(/[\p{Cc}\u200B\u2060\uFEFF\u202A-\u202E\u2066-\u2069]/gu, (c) => (c === '\n' ? c : ''))
    .replace(/[^\S\n]+\n/g, '\n') // trailing spaces, so blank lines are really blank
    .replace(/\n{4,}/g, '\n\n\n')
    .trim();
}

// Rejects http(s)://, www. and bare domains such as example.com or foo.xyz.
// A bare domain is one or more dot-separated labels followed by a top-level
// part of 2–24 letters written all lower case or all upper case (or xn--).
// So "example.com", "EXAMPLE.COM" and "mail@foo.xyz" are rejected, while
// "slop.Really" (a sentence run together) and "end. Next" are accepted.
// Trade-off: file names such as "image.png" are also rejected.
const LINK_RES = [
  /https?:\/\//i,
  /(?:^|[^\p{L}\p{N}])www\./iu,
  /(?:^|[^\p{L}\p{N}_-])(?:[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?\.)+(?:[a-z]{2,24}|[A-Z]{2,24}|xn--[a-z0-9-]+)(?![\p{L}\p{N}_-])/u,
];
export function looksLikeLink(text) {
  return LINK_RES.some((re) => re.test(text));
}

// HMAC-SHA256 keyed with RATE_SECRET + UTC date, over the IP; 128 bits in hex.
async function rateKey(secret, day, ip) {
  if (!secret) throw new Error('RATE_SECRET is not set');
  const enc = new TextEncoder();
  const k = await crypto.subtle.importKey('raw', enc.encode(secret + day), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = new Uint8Array(await crypto.subtle.sign('HMAC', k, enc.encode(ip)));
  return [...mac.slice(0, 16)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// Returns 'ok', 'failed' or 'unavailable'. The visitor IP is deliberately not sent.
async function verifyTurnstile(secret, token) {
  if (!secret) throw new Error('TURNSTILE_SECRET is not set');
  let res;
  try {
    res = await fetch(SITEVERIFY, {
      method: 'POST',
      body: new URLSearchParams({ secret, response: token }),
    });
  } catch {
    return 'unavailable';
  }
  if (!res.ok) return 'unavailable';
  const data = await res.json().catch(() => null);
  return data && data.success === true ? 'ok' : 'failed';
}

// Rate rows are only needed for the current UTC day; keep yesterday as slack.
async function pruneRate(env, now) {
  const yesterday = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);
  await env.DB.prepare('DELETE FROM rate WHERE day < ?').bind(yesterday).run();
}

function json(status, data, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      'Cache-Control': 'no-store',
      ...headers,
    },
  });
}

function error(status, message, headers) {
  return json(status, { error: message }, headers);
}
