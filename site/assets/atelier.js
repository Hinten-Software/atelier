// The atelier's pages read data/works.json (written by the export) and render it. Everything an artist wrote
// is set as text, never as HTML (requirements ATL-13).
const ROMAN = { i: "I", ii: "II", iii: "III" };
const MODELS = { "claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-fable-5-1": "Claude Fable 5.1" };
const STATES = {  // the open work's runner state, as a visitor sees it
  sitting: ["painting now", true], resumed: ["painting now", true], prepared: ["about to paint", false],
  between: ["resting between sittings", false], closed: ["resting", false], "limit-wait": ["resting", false],
  "crash-wait": ["resting", false], interrupted: ["resting", false], finishing: ["finishing", false],
};
const REFRESH_MS = 60_000;  // while a studio has a work open; the export runs every 2 minutes

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
const workHref = (w) => `/work/?w=${encodeURIComponent(w.id)}`;

async function data() {
  const r = await fetch("/data/works.json", { cache: "no-store" });
  return r.ok ? r.json() : { works: [], artists: [] };
}
async function looks() {  // the newest look of each work in progress (the viewer's index)
  try { const r = await fetch("/studio/data/sessions.json", { cache: "no-store" }); return r.ok ? r.json() : []; } catch { return []; }
}

// ---- where you are: Atelier / Studio III / the painting. Each step but the last is a link back.
function crumbs(...steps) {  // steps: [text, href] or [text]
  const top = document.querySelector("header.top");
  if (!top) return;
  top.replaceChildren(el("a", { href: "/", textContent: "Atelier" }));
  for (const [text, href] of steps) top.append(el("span", { class: "sep", textContent: "/" }), href ? el("a", { href, textContent: text }) : el("span", { textContent: text }));
}

// ---- a painting, close up: click to open, click or Esc to close; arrows (and swipe) when there are several
function lightbox(items, start) {  // items: [{src, title, href}]
  let i = start;
  const img = el("img", { alt: "" }), cap = el("p", { class: "cap" });
  const box = el("div", { class: "lightbox", role: "dialog", "aria-modal": "true", tabIndex: -1 }, img, cap);
  const prev = el("button", { class: "nav prev", type: "button", "aria-label": "Previous painting", textContent: "‹" });
  const next = el("button", { class: "nav next", type: "button", "aria-label": "Next painting", textContent: "›" });
  if (items.length > 1) box.append(prev, next);
  const show = () => {
    const it = items[i];
    img.src = it.src; img.alt = it.title || "";
    cap.replaceChildren(it.href ? el("a", { href: it.href, textContent: it.title || "Untitled" }) : it.title || "");
    if (items.length > 1) cap.append(el("span", { class: "state", textContent: `  ${i + 1} of ${items.length}` }));
  };
  const go = (d) => { i = (i + d + items.length) % items.length; show(); };
  const close = () => { box.remove(); document.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  const key = (e) => { if (e.key === "Escape") close(); else if (items.length > 1 && e.key === "ArrowLeft") go(-1); else if (items.length > 1 && e.key === "ArrowRight") go(1); };
  prev.onclick = (e) => { e.stopPropagation(); go(-1); };
  next.onclick = (e) => { e.stopPropagation(); go(1); };
  box.onclick = (e) => { if (!e.target.closest("a")) close(); };
  let x0 = null;
  box.ontouchstart = (e) => (x0 = e.touches[0].clientX);
  box.ontouchend = (e) => { if (x0 == null || items.length < 2) return; const dx = e.changedTouches[0].clientX - x0; x0 = null; if (Math.abs(dx) > 50) { e.preventDefault(); go(dx > 0 ? -1 : 1); } };
  document.addEventListener("keydown", key);
  document.body.style.overflow = "hidden";
  document.body.append(box); box.focus(); show();
}

// re-render while any studio has a work open, so a visitor who waits sees the painting change
function whileOpen(render) {
  let timer = null;
  const run = async () => { const open = await render(); clearTimeout(timer); if (open) timer = setTimeout(run, REFRESH_MS); };
  document.addEventListener("visibilitychange", () => { if (!document.hidden) run(); else clearTimeout(timer); });
  run();
}

function label(w) {
  return el("p", { class: "label" },
    el("span", { class: "title", textContent: w.title || "Untitled" }),
    `${studioName(artistOf(w.id))} · work ${w.number} · ${MODELS[w.model] || w.model || ""}${w.date ? " · " + day(w.date) : ""}`);
}

async function door() {
  const [d, ls] = await Promise.all([data(), looks()]);
  const box = document.getElementById("studios");
  const born = new Set(d.artists.map((a) => a.id));
  const cards = [];
  let anyOpen = false;
  for (const a of ["i", "ii", "iii"]) {
    const works = d.works.filter((w) => artistOf(w.id) === a);
    const open = works.find((w) => !w.finished && w.state);
    const done = works.filter((w) => w.finished).sort((x, y) => y.number - x.number);
    let img = null, state = "empty", live = false;
    if (born.has(a)) {
      [state, live] = open ? STATES[open.state] || ["resting", false] : ["idle", false];
      anyOpen ||= !!open;
      const look = open && ls.find((s) => s.p === open.viewer);
      const atBirth = d.artists.find((x) => x.id === a)?.walls_at_birth || 0;
      if (open && look && look.look != null) img = `/studio/data/${open.viewer}/v/${look.look}.jpg`;
      else if (done[0]) img = finalImg(done[0], true);
      else if (atBirth) img = `/studio/data/walls-${a}/${atBirth}.jpg`;
    }
    const frame = el("div", { class: "frame" }, img ? el("img", { src: img, alt: "", loading: "lazy" }) : el("span", { textContent: born.has(a) ? "" : "empty" }));
    const card = el(born.has(a) ? "a" : "div", { class: "studio" }, frame, el("h2", { textContent: studioName(a) }),
      el("div", { class: "state" + (live ? " live" : ""), textContent: state }));
    if (born.has(a)) card.href = `/walls/?s=${a}`;
    cards.push(card);
  }
  box.replaceChildren(...cards);
  return anyOpen;
}

async function walls() {
  const a = new URLSearchParams(location.search).get("s") || "i";
  const [d, ls] = await Promise.all([data(), looks()]);
  document.title = `${studioName(a)} · Atelier`;
  crumbs([studioName(a)]);
  document.getElementById("name").textContent = studioName(a);
  const works = d.works.filter((w) => artistOf(w.id) === a);
  const open = works.find((w) => !w.finished && w.state);
  const easel = document.getElementById("easel");
  easel.replaceChildren();
  if (open) {  // the canvas as they last looked at it, and the way in to watch
    const [state, live] = STATES[open.state] || ["resting", false];
    const watch = `/studio/?p=${encodeURIComponent(open.viewer)}`;
    const look = ls.find((x) => x.p === open.viewer);
    if (look && look.look != null) easel.append(el("a", { href: watch, class: "canvas" }, el("img", { src: `/studio/data/${open.viewer}/v/${look.look}.jpg`, alt: "The painting in progress" })));
    easel.append(el("div", { class: "state" + (live ? " live" : ""), textContent: `On the easel: work ${open.number}, ${state}` }), " ",
      el("a", { href: watch, textContent: live ? "Watch" : "See it so far", class: "state" }));
  }
  // newest first, wrapping like a hang on a wall; what hung there before their first work comes last
  const done = works.filter((w) => w.finished).sort((x, y) => y.number - x.number);
  const birth = d.artists.find((x) => x.id === a) || {};
  const items = done.map((w) => ({ src: finalImg(w), title: w.title || "Untitled", href: workHref(w) }));
  const atBirth = [];
  for (let n = birth.walls_at_birth || 0; n >= 1; n--) atBirth.push({ src: `/studio/data/walls-${a}/${n}.jpg`, title: String(n) });
  const all = [...items, ...atBirth];
  if (birth.temperament_note) easel.append(el("p", { class: "state", textContent: birth.temperament_note }));
  const box = document.getElementById("walls");
  const kids = [];
  if (!all.length) kids.push(el("p", { class: "empty", textContent: "The walls are bare." }));
  done.forEach((w, k) => kids.push(el("figure", {},
    el("img", { src: finalImg(w, true), alt: w.title || "Untitled", loading: "lazy", onclick: () => lightbox(all, k) }),
    el("figcaption", {}, el("a", { href: workHref(w), class: "t", textContent: w.title || "Untitled" }),
      el("div", { class: "state", textContent: `work ${w.number}${w.date ? " · " + day(w.date) : ""}` })))));
  if (atBirth.length) {
    kids.push(el("p", { class: "state hung", textContent: birth.walls_note }));
    atBirth.forEach((it, k) => kids.push(el("figure", {},
      el("img", { src: it.src, alt: "", loading: "lazy", onclick: () => lightbox(all, items.length + k) }),
      el("figcaption", {}, el("div", { class: "t", textContent: it.title })))));
  }
  box.replaceChildren(...kids);
  return !!open;
}

async function work() {
  const id = new URLSearchParams(location.search).get("w") || "";
  const d = await data();
  const w = d.works.find((x) => x.id === id && x.finished);
  const box = document.getElementById("work");
  if (!w) { box.append(el("p", { class: "empty", textContent: "Nothing hangs here." })); return; }
  const a = artistOf(w.id);
  document.title = `${w.title || "Untitled"} · Atelier`;
  crumbs([studioName(a), `/walls/?s=${a}`], [w.title || "Untitled"]);
  const img = el("img", { src: finalImg(w), alt: w.title || "Untitled", onclick: () => lightbox([{ src: finalImg(w), title: w.title || "Untitled" }], 0) });
  box.append(el("div", { class: "piece" }, img, label(w)));
  box.append(el("p", { class: "actions" }, el("a", { href: `/studio/?p=${encodeURIComponent(w.viewer)}`, textContent: "Watch it being painted" })));
  if (w.theme) box.append(el("div", { class: "words" }, el("h2", { textContent: "They were given" }), el("p", { textContent: w.theme })));
  if (w.reply) box.append(el("div", { class: "words" }, el("h2", { textContent: "The painter's words" }), el("p", { textContent: plain(w.reply) })));
}

// ---- notes: one guestbook for the whole atelier (/notes/). Plain text in, plain text out (ATL-13).
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

async function notes(box) {
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
    const item = el("article", { class: "note" }, el("p", { textContent: n.text }), el("div", { class: "state", textContent: when(n.at) }));
    top ? list.prepend(item) : list.append(item);
  };
  async function page() {
    const q = new URLSearchParams(); if (next) q.set("before", next);
    try {
      const r = await fetch(`${NOTES_API}?${q}`);
      if (!r.ok) throw new Error();
      const d = await r.json();
      d.notes.forEach((n) => show(n, false));
      next = d.next; more.hidden = !next;
      if (!d.notes.length && !list.children.length) list.append(el("p", { class: "empty", textContent: "No notes yet." }));
    } catch { form.hidden = true; list.replaceChildren(el("p", { class: "empty", textContent: "The notes are closed for now." })); }
  }
  more.onclick = page;
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!token) { said.textContent = "Please complete the check first."; return; }
    send.disabled = true; said.textContent = "";
    try {
      const r = await fetch(NOTES_API, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.value, work: null, token }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { said.textContent = d.error || "Something went wrong. Please try again later."; return; }
      list.querySelector(".empty")?.remove();
      show({ id: d.id, at: d.at, text: text.value.trim() }, true);  // the wall's copy is 30 s behind
      text.value = ""; count.textContent = "500"; said.textContent = "Your note is on the wall.";
    } finally {
      send.disabled = false;
      if (SITE_KEY !== "preview") { token = null; if (widget != null) window.turnstile.reset(widget); }
    }
  };
  await page();
}

const pages = {
  door: () => whileOpen(door),
  walls: () => whileOpen(walls),
  work,
  notes: () => notes(document.getElementById("notes")),
};
pages[document.body.dataset.page]?.();
