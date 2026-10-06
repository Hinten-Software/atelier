// Run with: node --test deploy/notes/test/
// The fake D1 wraps node:sqlite in memory, so the Worker's real SQL and
// schema.sql are exercised. Turnstile is a stubbed global fetch.

import { test, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import worker, { cleanText, looksLikeLink } from '../worker.js';

const SCHEMA = readFileSync(new URL('../schema.sql', import.meta.url), 'utf8');
const IP = '203.0.113.77';
const UA = 'Mozilla/5.0 (Probe; NotesTest/1.0)';
const COUNTRY = 'XQ';

class FakeD1 {
  constructor() {
    this.sqlite = new DatabaseSync(':memory:');
    this.sqlite.exec(SCHEMA);
  }
  prepare(sql) { return new FakeStatement(this.sqlite, sql, []); }
  // Every table and every cell, for privacy assertions.
  dump() {
    const tables = this.sqlite.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all();
    return Object.fromEntries(tables.map(({ name }) => [name, this.sqlite.prepare(`SELECT * FROM "${name}"`).all().map((r) => ({ ...r }))]));
  }
}

class FakeStatement {
  constructor(sqlite, sql, args) { Object.assign(this, { sqlite, sql, args }); }
  bind(...args) { return new FakeStatement(this.sqlite, this.sql, args); }
  async all() { return { success: true, meta: {}, results: this.sqlite.prepare(this.sql).all(...this.args).map((r) => ({ ...r })) }; }
  async first(column) {
    const row = this.sqlite.prepare(this.sql).get(...this.args);
    if (!row) return null;
    return column ? row[column] : { ...row };
  }
  async run() {
    const r = this.sqlite.prepare(this.sql).run(...this.args);
    return { success: true, meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } };
  }
}

let env, ctx, siteverifyCalls, realFetch;

beforeEach(() => {
  env = { DB: new FakeD1(), TURNSTILE_SECRET: 'test-turnstile-secret', RATE_SECRET: 'test-rate-secret' };
  const pending = [];
  ctx = { waitUntil: (p) => pending.push(p), settle: () => Promise.all(pending.splice(0)) };
  siteverifyCalls = [];
  realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url), 'https://challenges.cloudflare.com/turnstile/v0/siteverify');
    const form = new URLSearchParams(String(init.body));
    siteverifyCalls.push(Object.fromEntries(form));
    return Response.json({ success: form.get('response') === 'good-token' && form.get('secret') === env.TURNSTILE_SECRET });
  };
});

afterEach(() => {
  globalThis.fetch = realFetch;
  mock.timers.reset();
});

async function call(method, path, { body, ip = IP, headers = {} } = {}) {
  const init = {
    method,
    headers: { 'CF-Connecting-IP': ip, 'User-Agent': UA, 'CF-IPCountry': COUNTRY, ...headers },
  };
  if (body !== undefined) {
    init.body = typeof body === 'string' ? body : JSON.stringify(body);
    init.headers['Content-Type'] = 'application/json';
  }
  const res = await worker.fetch(new Request('https://notart.fyi' + path, init), env, ctx);
  await ctx.settle();
  const text = await res.text();
  return { status: res.status, headers: res.headers, data: text ? JSON.parse(text) : null };
}

const post = (fields, opts) => call('POST', '/api/notes', { body: { token: 'good-token', ...fields }, ...opts });

// Inserts notes directly, bypassing rate limits. Returns their ids.
function seed(rows) {
  const stmt = env.DB.sqlite.prepare('INSERT INTO notes (at, work, text, hidden) VALUES (?, ?, ?, ?)');
  return rows.map((r) => Number(stmt.run(r.at ?? '2026-10-01T12:00Z', r.work ?? null, r.text ?? 'hi', r.hidden ?? 0).lastInsertRowid));
}

// ---------------------------------------------------------------- POST

test('valid post is stored and returned as 201 {id, at}', async () => {
  mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-10-06T07:31:45.123Z') });
  const r = await post({ text: '  I hate this one.  ', work: 'field-012' });
  assert.equal(r.status, 201);
  assert.deepEqual(r.data, { id: 1, at: '2026-10-06T07:31Z' });
  assert.equal(r.headers.get('Cache-Control'), 'no-store');
  assert.equal(r.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.match(r.headers.get('Content-Type'), /^application\/json/);
  assert.deepEqual(env.DB.dump().notes, [{ id: 1, at: '2026-10-06T07:31Z', work: 'field-012', text: 'I hate this one.', hidden: 0 }]);

  const wall = await post({ text: 'For the wall' });
  assert.equal(wall.status, 201);
  assert.equal(env.DB.dump().notes[1].work, null);
});

test('text is cleaned: control characters removed, newlines capped at 3', async () => {
  const r = await post({ text: 'a\u0000b\u0007\tc\r\n\r\n\r\n\r\n\n\nd‮e' });
  assert.equal(r.status, 201);
  assert.equal(env.DB.dump().notes[0].text, 'abc\n\n\nde');
  assert.equal(cleanText('x  \n \n \n \n \ny'), 'x\n\n\ny');
});

test('empty, whitespace-only and too long text is rejected', async () => {
  for (const text of ['', '   \n\n  ', '\u0000\u0001']) {
    const r = await post({ text });
    assert.equal(r.status, 400, JSON.stringify(text));
    assert.equal(r.data.error, 'Please write something.');
    assert.equal(r.headers.get('Cache-Control'), 'no-store');
  }
  assert.equal((await post({})).status, 400);
  assert.equal((await post({ text: 42 })).status, 400);

  const long = await post({ text: 'x'.repeat(501) });
  assert.equal(long.status, 400);
  assert.match(long.data.error, /500 characters/);

  // 500 code points are fine even when they are astral (2 UTF-16 units each).
  assert.equal((await post({ text: '🎨'.repeat(500) })).status, 201);
  assert.equal((await post({ text: '🎨'.repeat(501) })).status, 400);
  assert.equal(siteverifyCalls.length, 1, 'invalid input never reaches Turnstile');
});

test('bodies over 4 KB and malformed JSON are rejected', async () => {
  const big = await call('POST', '/api/notes', { body: JSON.stringify({ text: 'x', token: 'good-token', pad: 'p'.repeat(4096) }) });
  assert.equal(big.status, 400);
  assert.equal((await call('POST', '/api/notes', { body: '{nope' })).status, 400);
  assert.equal((await call('POST', '/api/notes', { body: '[1,2]' })).status, 400);
  assert.equal(env.DB.dump().notes.length, 0);
});

test('links are rejected, ordinary prose is not', () => {
  const links = [
    'see http://x', 'HTTPS://EXAMPLE.ORG', 'go to www.something', 'example.com', 'visit foo.xyz now',
    'EXAMPLE.COM', 'mail me: me@mail.example.net', 'sub.domain.co.uk/path', 'bücher.de', 'xn--bcher-kva.xn--p1ai',
    'end of line\nexample.com.',
  ];
  const prose = [
    'This is slop. Really.', 'slop.Really', 'Wait...what', 'e.g. this', 'i.e. that', 'version 1.2.3',
    'it costs 3.50', 'field-012 is the best', 'Hello.World', 'a.b', 'ok.\nnext', 'Mr. Smith',
  ];
  for (const t of links) assert.equal(looksLikeLink(t), true, `should reject: ${t}`);
  for (const t of prose) assert.equal(looksLikeLink(t), false, `should accept: ${t}`);
});

test('a note containing a link gets 400', async () => {
  const r = await post({ text: 'buy cheap at example.com' });
  assert.equal(r.status, 400);
  assert.equal(r.data.error, 'Links are not allowed.');
  assert.equal(env.DB.dump().notes.length, 0);
});

test('bad work ids are rejected', async () => {
  for (const work of ['Field-012', 'field-12', 'field-0123', 'field012', '../x', 'field-012 ', 7, ['field-012']]) {
    const r = await post({ text: 'hello', work });
    assert.equal(r.status, 400, JSON.stringify(work));
    assert.equal(r.data.error, 'Unknown work.');
  }
  assert.equal((await post({ text: 'hello', work: null })).status, 201);
});

test('Turnstile failure gives 403 and stores nothing; IP is never sent', async () => {
  const bad = await post({ text: 'hello', token: 'forged' });
  assert.equal(bad.status, 403);
  assert.equal((await post({ text: 'hello', token: '' })).status, 403);
  assert.equal((await post({ text: 'hello', token: undefined })).status, 403);
  assert.equal((await post({ text: 'hello', token: 'x'.repeat(2049) })).status, 403);
  assert.equal(env.DB.dump().notes.length, 0);
  assert.equal(env.DB.dump().rate.length, 0, 'failed checks do not use up the limit');

  await post({ text: 'hello' });
  for (const c of siteverifyCalls) {
    assert.deepEqual(Object.keys(c).sort(), ['response', 'secret']);
    assert.ok(!JSON.stringify(c).includes(IP));
  }
});

test('Turnstile outage gives 503', async () => {
  globalThis.fetch = async () => { throw new TypeError('network down'); };
  const r = await post({ text: 'hello' });
  assert.equal(r.status, 503);
  assert.equal(env.DB.dump().notes.length, 0);
});

test('rate limit: the 6th note within an hour is 429, other visitors unaffected', async () => {
  mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-10-06T07:05:00Z') });
  for (let i = 1; i <= 5; i++) assert.equal((await post({ text: `note ${i}` })).status, 201);
  const sixth = await post({ text: 'note 6' });
  assert.equal(sixth.status, 429);
  assert.equal(sixth.headers.get('Cache-Control'), 'no-store');
  assert.equal(siteverifyCalls.length, 5, 'limited requests do not reach Turnstile');
  assert.equal((await post({ text: 'other' }, { ip: '198.51.100.9' })).status, 201);

  mock.timers.setTime(Date.parse('2026-10-06T08:00:00Z'));
  assert.equal((await post({ text: 'next hour' })).status, 201);
});

test('rate limit: 20 notes per UTC day, reset the next day', async () => {
  mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-10-06T00:10:00Z') });
  let ok = 0;
  for (let h = 0; h < 5; h++) {
    mock.timers.setTime(Date.parse(`2026-10-06T0${h}:10:00Z`));
    for (let i = 0; i < 5; i++) if ((await post({ text: `n${h}.${i}` })).status === 201) ok++;
  }
  assert.equal(ok, 20);
  mock.timers.setTime(Date.parse('2026-10-07T00:10:00Z'));
  assert.equal((await post({ text: 'new day' })).status, 201);
});

test('old rate rows are pruned on write and by the scheduled handler', async () => {
  env.DB.sqlite.exec("INSERT INTO rate VALUES ('old', '2026-10-03', '2026-10-03T10', 3), ('yday', '2026-10-05', '2026-10-05T10', 1)");
  mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-10-06T07:00:00Z') });
  await post({ text: 'hello' });
  assert.deepEqual(env.DB.dump().rate.map((r) => r.key).filter((k) => k.length < 10), ['yday']);

  mock.timers.setTime(Date.parse('2026-10-08T03:00:00Z'));
  await worker.scheduled({ cron: '17 3 * * *' }, env, ctx);
  await ctx.settle();
  assert.equal(env.DB.dump().rate.length, 0);
});

// ---------------------------------------------------------------- GET

test('GET returns newest first, 50 per page, with a working cursor', async () => {
  seed(Array.from({ length: 120 }, (_, i) => ({ text: `note ${i + 1}` })));
  const p1 = await call('GET', '/api/notes');
  assert.equal(p1.status, 200);
  assert.equal(p1.headers.get('Cache-Control'), 'public, max-age=30');
  assert.equal(p1.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.equal(p1.data.notes.length, 50);
  assert.deepEqual(p1.data.notes[0], { id: 120, at: '2026-10-01T12:00Z', work: null, text: 'note 120' });
  assert.equal(p1.data.next, '71');

  const p2 = await call('GET', `/api/notes?before=${p1.data.next}`);
  assert.equal(p2.data.notes[0].id, 70);
  const p3 = await call('GET', `/api/notes?before=${p2.data.next}`);
  assert.equal(p3.data.notes.length, 20);
  assert.equal(p3.data.notes.at(-1).id, 1);
  assert.equal(p3.data.next, null);
});

test('exactly 50 notes means no next page', async () => {
  seed(Array.from({ length: 50 }, () => ({})));
  const r = await call('GET', '/api/notes');
  assert.equal(r.data.notes.length, 50);
  assert.equal(r.data.next, null);
});

test('GET filters by work; the wall shows everything', async () => {
  seed([{ work: 'field-012', text: 'a' }, { text: 'wall' }, { work: 'field-013', text: 'b' }, { work: 'field-012', text: 'c' }]);
  const one = await call('GET', '/api/notes?work=field-012');
  assert.deepEqual(one.data.notes.map((n) => n.text), ['c', 'a']);
  const wall = await call('GET', '/api/notes');
  assert.deepEqual(wall.data.notes.map((n) => n.text), ['c', 'b', 'wall', 'a']);
  assert.deepEqual((await call('GET', '/api/notes?work=none-999')).data, { notes: [], next: null });
});

test('GET rejects bad parameters', async () => {
  for (const q of ['work=FIELD-1', 'work=', 'before=0', 'before=abc', 'before=-3', 'before=1e3']) {
    const r = await call('GET', `/api/notes?${q}`);
    assert.equal(r.status, 400, q);
    assert.equal(r.headers.get('Cache-Control'), 'no-store');
  }
});

test('hidden notes are never returned', async () => {
  seed([{ text: 'keep' }, { text: 'spam', hidden: 1 }, { text: 'spam too', work: 'field-012', hidden: 1 }, { text: 'mine', work: 'field-012' }]);
  const wall = await call('GET', '/api/notes');
  assert.deepEqual(wall.data.notes.map((n) => n.text), ['mine', 'keep']);
  const work = await call('GET', '/api/notes?work=field-012');
  assert.deepEqual(work.data.notes.map((n) => n.text), ['mine']);
  assert.ok(!('hidden' in wall.data.notes[0]));
});

test('hostile notes stay: a posted note is visible on the wall', async () => {
  await post({ text: 'This is terrible art and you should stop.' });
  const wall = await call('GET', '/api/notes');
  assert.equal(wall.data.notes[0].text, 'This is terrible art and you should stop.');
});

// ---------------------------------------------------------------- privacy

test('nothing identifying is stored anywhere', async () => {
  for (let i = 0; i < 3; i++) await post({ text: `note ${i}` });
  await post({ text: 'other', work: 'field-012' }, { ip: '2001:db8::1', headers: { Referer: 'https://notart.fyi/field-012' } });
  const dump = env.DB.dump();
  assert.deepEqual(Object.keys(dump).sort(), ['notes', 'rate']);
  assert.deepEqual(Object.keys(dump.notes[0]).sort(), ['at', 'hidden', 'id', 'text', 'work']);
  assert.deepEqual(Object.keys(dump.rate[0]).sort(), ['count', 'day', 'hour', 'key']);

  const everything = JSON.stringify(dump);
  for (const secret of [IP, '203.0.113', '2001:db8', UA, 'Mozilla', COUNTRY, 'Referer', 'notart.fyi/field', env.RATE_SECRET]) {
    assert.ok(!everything.includes(secret), `found ${secret} in the database`);
  }
  for (const row of dump.rate) assert.match(row.key, /^[0-9a-f]{32}$/);
  assert.equal(new Set(dump.rate.map((r) => r.key)).size, 2, 'one key per visitor');
});

// ---------------------------------------------------------------- routing

test('other methods get 405, other paths 404', async () => {
  for (const method of ['PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']) {
    const r = await call(method, '/api/notes');
    assert.equal(r.status, 405, method);
    assert.equal(r.headers.get('Allow'), 'GET, POST');
    assert.equal(r.headers.get('Cache-Control'), 'no-store');
    assert.equal(r.headers.get('X-Content-Type-Options'), 'nosniff');
  }
  for (const path of ['/', '/api/notes/1', '/api/notesx', '/api/notes/', '/api/other']) {
    const r = await call('GET', path);
    assert.equal(r.status, 404, path);
    assert.deepEqual(r.data, { error: 'Not found.' });
  }
});
