// The atelier's pages read data/works.json (written by the export) and render it. Everything an artist wrote
// is set as text, never as HTML (requirements ATL-13).
const ROMAN = { i: "I", ii: "II", iii: "III" };
const MODELS = { "claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-fable-5-1": "Claude Fable 5.1" };
const STATES = {  // the open work's runner state, as a visitor sees it
  sitting: ["painting now", true], resumed: ["painting now", true], prepared: ["about to paint", false],
  between: ["resting between sittings", false], closed: ["resting", false], "limit-wait": ["resting", false],
  "crash-wait": ["resting", false], interrupted: ["resting", false], finishing: ["finishing", false],
};

const el = (tag, props = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) k === "class" ? (e.className = v) : k.includes("-") ? e.setAttribute(k, v) : (e[k] = v);
  for (const k of kids) if (k != null) e.append(k);
  return e;
};
const artistOf = (id) => id.split("-")[0];
const studioName = (a) => `Studio ${ROMAN[a] || a.toUpperCase()}`;
const plain = (s) => (s || "").replace(/\*\*(.+?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");
const day = (iso) => iso ? new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }) : "";
const finalImg = (w, small) => `/studio/data/${w.viewer}/${small ? "final-t.jpg" : "final.jpg"}`;

async function data() {
  const r = await fetch("/data/works.json", { cache: "no-store" });
  return r.ok ? r.json() : { works: [], artists: [] };
}
async function looks() {  // the newest look of each work in progress (the viewer's index)
  try { const r = await fetch("/studio/data/sessions.json", { cache: "no-store" }); return r.ok ? r.json() : []; } catch { return []; }
}

function label(w) {
  return el("p", { class: "label" },
    el("span", { class: "title", textContent: w.title || "Untitled" }),
    `${studioName(artistOf(w.id))} · work ${w.number} · ${MODELS[w.model] || w.model || ""}${w.date ? " · " + day(w.date) : ""}`,
    el("span", { class: "fact", textContent: "The painter does not know you are here." }));
}

async function door() {
  const [d, ls] = await Promise.all([data(), looks()]);
  const box = document.getElementById("studios");
  const born = new Set(d.artists.map((a) => a.id));
  for (const a of ["i", "ii", "iii"]) {
    const works = d.works.filter((w) => artistOf(w.id) === a);
    const open = works.find((w) => !w.finished && w.state);
    const done = works.filter((w) => w.finished).sort((x, y) => y.number - x.number);
    let img = null, state = "empty", live = false;
    if (born.has(a)) {
      [state, live] = open ? STATES[open.state] || ["resting", false] : ["idle", false];
      const look = open && ls.find((s) => s.p === open.viewer);
      if (open && look && look.look != null) img = `/studio/data/${open.viewer}/v/${look.look}.jpg`;
      else if (done[0]) img = finalImg(done[0], true);
    }
    const frame = el("div", { class: "frame" }, img ? el("img", { src: img, alt: "", loading: "lazy" }) : el("span", { textContent: born.has(a) ? "" : "empty" }));
    const card = el(born.has(a) ? "a" : "div", { class: "studio" }, frame, el("h2", { textContent: studioName(a) }),
      el("div", { class: "state" + (live ? " live" : ""), textContent: state }));
    if (born.has(a)) card.href = `/walls/?s=${a}`;
    box.append(card);
  }
}

async function walls() {
  const a = new URLSearchParams(location.search).get("s") || "i";
  const d = await data();
  document.title = `${studioName(a)} · Atelier`;
  document.getElementById("name").textContent = studioName(a);
  const works = d.works.filter((w) => artistOf(w.id) === a);
  const open = works.find((w) => !w.finished && w.state);
  const easel = document.getElementById("easel");
  if (open) {
    const [state, live] = STATES[open.state] || ["resting", false];
    easel.append(el("div", { class: "state" + (live ? " live" : ""), textContent: `On the easel: work ${open.number}, ${state}` }), " ",
      el("a", { href: `/studio/?p=${encodeURIComponent(open.viewer)}`, textContent: live ? "Watch" : "See it so far", class: "state" }));
  }
  const box = document.getElementById("walls");
  const done = works.filter((w) => w.finished).sort((x, y) => x.number - y.number);  // a timeline: oldest left
  if (!done.length) box.append(el("p", { class: "empty", textContent: "The walls are bare." }));
  for (const w of done)
    box.append(el("a", { href: `/work/?w=${encodeURIComponent(w.id)}` }, el("img", { src: finalImg(w, true), alt: w.title || "Untitled", loading: "lazy" }),
      el("div", { class: "t", textContent: w.title || "Untitled" }), el("div", { class: "state", textContent: `work ${w.number}${w.date ? " · " + day(w.date) : ""}` })));
}

async function work() {
  const id = new URLSearchParams(location.search).get("w") || "";
  const d = await data();
  const w = d.works.find((x) => x.id === id && x.finished);
  const box = document.getElementById("work");
  if (!w) { box.append(el("p", { class: "empty", textContent: "Nothing hangs here." })); return; }
  document.title = `${w.title || "Untitled"} · Atelier`;
  box.append(el("div", { class: "piece" }, el("a", { href: `/studio/data/${w.viewer}/final.png` }, el("img", { src: finalImg(w), alt: w.title || "Untitled" })), label(w)));
  box.append(el("p", { class: "actions" }, el("a", { href: `/studio/?p=${encodeURIComponent(w.viewer)}`, textContent: "Watch it being painted" }),
    " · ", el("a", { href: `/walls/?s=${artistOf(w.id)}`, textContent: `${studioName(artistOf(w.id))}'s walls` })));
  if (w.theme) box.append(el("div", { class: "words" }, el("h2", { textContent: "They were given" }), el("p", { textContent: w.theme })));
  if (w.reply) box.append(el("div", { class: "words" }, el("h2", { textContent: "The painter's words" }), el("p", { textContent: plain(w.reply) })));
  const n = el("section", { class: "words notes-on-work" }, el("h2", { textContent: "Notes" }));
  box.append(n);
  notes(n, w.id, {});
}

// ---- notes: visitors' words, on the wall (/notes/) and under a work. Plain text in, plain text out (ATL-13).
const NOTES_API = "/api/notes";
const SITE_KEY = document.querySelector('meta[name="turnstile"]')?.content || "";
let turnstileReady = null;
function loadTurnstile() {  // the bot check, loaded only where a note can be left; "preview": the local preview, none
  if (SITE_KEY === "preview" || !SITE_KEY || SITE_KEY === "TURNSTILE_SITE_KEY") return Promise.resolve(null);
  return turnstileReady ??= new Promise((ok) => {
    window.onTurnstile = () => ok(window.turnstile);
    document.head.append(el("script", { src: "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onTurnstile", async: true }));
  });
}
const when = (at) => { const d = new Date(at.replace("Z", ":00Z")); return isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }); };

async function notes(box, workId, titles) {
  const list = el("div", { class: "note-list" }), more = el("button", { class: "more", type: "button", textContent: "Older notes", hidden: true });
  const form = el("form", { class: "note-form" });
  const text = el("textarea", { name: "text", maxLength: 500, rows: 4, required: true, "aria-label": "Your note" });
  const count = el("span", { class: "count", textContent: "500" }), check = el("div", { class: "check" });
  const send = el("button", { type: "submit", textContent: "Leave it" }), said = el("p", { class: "said", role: "status" });
  form.append(el("p", { class: "invite", textContent: "Leave a note. No name, no account. It will be shown as written." }), text,
    el("div", { class: "row" }, check, count, send), said);
  box.append(form, list, more);
  let token = SITE_KEY === "preview" ? "preview" : null, widget = null, next = null;
  text.oninput = () => (count.textContent = String(500 - [...text.value].length));
  loadTurnstile().then((t) => { if (t) widget = t.render(check, { sitekey: SITE_KEY, callback: (v) => (token = v), "expired-callback": () => (token = null) }); });

  const show = (n, top) => {
    const meta = [when(n.at)];
    const item = el("article", { class: "note" }, el("p", { textContent: n.text }));
    if (n.work && !workId) {
      const a = el("a", { href: `/work/?w=${encodeURIComponent(n.work)}`, textContent: titles[n.work] || "a painting" });
      item.append(el("div", { class: "state" }, `${meta[0]} · on `, a));
    } else item.append(el("div", { class: "state", textContent: meta[0] }));
    top ? list.prepend(item) : list.append(item);
  };
  async function page() {
    const q = new URLSearchParams(); if (workId) q.set("work", workId); if (next) q.set("before", next);
    try {
      const r = await fetch(`${NOTES_API}?${q}`);
      if (!r.ok) throw new Error();
      const d = await r.json();
      d.notes.forEach((n) => show(n, false));
      next = d.next; more.hidden = !next;
      if (!d.notes.length && !list.children.length) list.append(el("p", { class: "empty", textContent: workId ? "No notes on this painting yet." : "No notes yet." }));
    } catch { form.hidden = true; list.replaceChildren(el("p", { class: "empty", textContent: "The notes are closed for now." })); }
  }
  more.onclick = page;
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!token) { said.textContent = "Please complete the check first."; return; }
    send.disabled = true; said.textContent = "";
    try {
      const r = await fetch(NOTES_API, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.value, work: workId || null, token }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { said.textContent = d.error || "Something went wrong. Please try again later."; return; }
      list.querySelector(".empty")?.remove();
      show({ id: d.id, at: d.at, work: workId || null, text: text.value.trim() }, true);  // the wall's copy is 30 s behind
      text.value = ""; count.textContent = "500"; said.textContent = "Your note is on the wall.";
    } finally {
      send.disabled = false;
      if (SITE_KEY !== "preview") { token = null; if (widget != null) window.turnstile.reset(widget); }
    }
  };
  await page();
}

async function notesPage() {
  const d = await data();
  notes(document.getElementById("notes"), null, Object.fromEntries(d.works.map((w) => [w.id, w.title || "Untitled"])));
}

({ door, walls, work, notes: notesPage })[document.body.dataset.page]?.();
