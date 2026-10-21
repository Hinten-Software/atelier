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
const IDLE_MS = 300_000;    // while none has: often enough that a page left open sees the next work begin

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
// the season a painting was finished in, as the walls group them: Winter runs December to February
const season = (iso) => {
  if (!iso) return "Undated";
  const [y, m] = iso.split("-").map(Number);
  if (m === 12) return `Winter ${y}–${String(y + 1).slice(2)}`;
  if (m <= 2) return `Winter ${y - 1}–${String(y).slice(2)}`;
  return `${m <= 5 ? "Spring" : m <= 8 ? "Summer" : "Autumn"} ${y}`;
};
const finalImg = (w, small) => `/studio/data/${w.viewer}/${small ? "final-t.jpg" : "final.jpg"}`;
const fullImg = (w) => `/studio/data/${w.viewer}/final-f.jpg`;  // the whole painting, every pixel
// a zoomed page or a dense screen takes the full-size copy by itself; the plain one serves everyone else
const srcsetOf = (w) => w.px ? `${finalImg(w)} 1600w, ${fullImg(w)} ${w.px}w` : "";
const closeUp = (w) => ({ src: finalImg(w), srcset: srcsetOf(w), full: w.px ? fullImg(w) : null, px: w.px, title: w.title || "Untitled", href: workHref(w), measure: measure(w) });
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

// ---- a painting, close up: click to open; click the painting again to see it at full size, every pixel of it, and
// move about in it (scroll, drag on a phone); click once more to see it whole. A click beside it, or Esc, closes.
// Arrows (and swipe) when there are several. Nothing more to find: no buttons, no links.
function lightbox(items, start) {  // items: [{src, srcset, full, title, href}]
  let i = start;
  const img = el("img", { alt: "" }), cap = el("p", { class: "cap" });
  const box = el("div", { class: "lightbox", role: "dialog", "aria-modal": "true", tabIndex: -1 }, img, cap);
  const prev = el("button", { class: "nav prev", type: "button", "aria-label": "Previous painting", textContent: "‹" });
  const next = el("button", { class: "nav next", type: "button", "aria-label": "Next painting", textContent: "›" });
  if (items.length > 1) box.append(prev, next);
  const show = () => {
    const it = items[i];
    box.classList.remove("full"); img.style.width = img.style.height = ""; box.scrollTop = box.scrollLeft = 0;
    img.srcset = it.srcset || ""; img.sizes = it.srcset ? "(max-width: 640px) 100vw, 1600px" : "";  // as large as it may be shown: browser zoom enlarges it
    img.src = it.src; img.alt = it.title || "";
    img.style.cursor = it.full ? "zoom-in" : "zoom-out";
    cap.replaceChildren(it.href ? el("a", { href: it.href, textContent: it.title || "Untitled" }) : it.title || "");
    if (it.measure) cap.append(el("span", { class: "state", textContent: ` · ${it.measure}` }));
    if (items.length > 1) cap.append(el("span", { class: "state", textContent: `  ${i + 1} of ${items.length}` }));
  };
  const go = (d) => { i = (i + d + items.length) % items.length; show(); };
  const close = () => { box.remove(); document.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  const whole = () => show();
  const fullSize = (e) => {  // where the click fell stays under the pointer: that is where they wanted to look
    const it = items[i], r = img.getBoundingClientRect(), b = box.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    const w = it.px / (window.devicePixelRatio || 1), h = w * r.height / r.width;  // one painting pixel, one screen pixel
    box.classList.add("full");
    img.removeAttribute("srcset"); img.removeAttribute("sizes");
    img.src = it.full; img.style.width = `${w}px`; img.style.height = `${h}px`; img.style.cursor = "zoom-out";
    box.scrollLeft = fx * w - (e.clientX - b.left);
    box.scrollTop = fy * h - (e.clientY - b.top);
  };
  img.onclick = (e) => {
    e.stopPropagation();
    if (box.classList.contains("full")) whole();
    else if (items[i].full && items[i].px) fullSize(e);
    else close();
  };
  const key = (e) => { if (e.key === "Escape") box.classList.contains("full") ? whole() : close(); else if (items.length > 1 && e.key === "ArrowLeft") go(-1); else if (items.length > 1 && e.key === "ArrowRight") go(1); };
  prev.onclick = (e) => { e.stopPropagation(); go(-1); };
  next.onclick = (e) => { e.stopPropagation(); go(1); };
  box.onclick = (e) => { if (!e.target.closest("a")) close(); };
  let x0 = null;
  box.ontouchstart = (e) => (x0 = e.touches[0].clientX);
  box.ontouchend = (e) => { if (x0 == null || items.length < 2 || box.classList.contains("full")) return; const dx = e.changedTouches[0].clientX - x0; x0 = null; if (Math.abs(dx) > 50) { e.preventDefault(); go(dx > 0 ? -1 : 1); } };
  document.addEventListener("keydown", key);
  document.body.style.overflow = "hidden";
  document.body.append(box); box.focus(); show();
}

// re-render every minute while any studio has a work open, so a visitor who waits sees the painting change, and
// every five minutes while none has, so they see the next work begin
function whileOpen(render) {
  let timer = null;
  const run = async () => { const open = await render(); clearTimeout(timer); timer = setTimeout(run, open ? REFRESH_MS : IDLE_MS); };
  document.addEventListener("visibilitychange", () => { if (!document.hidden) run(); else clearTimeout(timer); });
  run();
}

// a text in full, as written (set as text, ATL-13), folded under a quiet heading below the paintings; opened, it
// reads in a bounded scroll area instead of pushing the page on. text: a string, or paragraphs already made
function written(heading, text) {
  const area = el("div", { class: "scroll", tabIndex: 0, "aria-label": heading },
    ...(typeof text === "string" ? [el("pre", { textContent: text.trim() })] : text));
  area.setAttribute("role", "region");  // focusable, so it scrolls from the keyboard too
  return el("details", { class: "written" }, el("summary", { textContent: heading }), area);
}

// texts that live through the minute's refresh: a block whose words did not change is the same node, left in place
// (open or folded, scrolled where the reader left it); one that changed is made anew, open if the reader had it open
const kept = new Map();  // key -> {sig, node}
function steady(box, blocks) {  // blocks: [key, sig, make]
  const keys = new Set(blocks.map(([key]) => key));
  for (const key of kept.keys()) if (!keys.has(key)) kept.delete(key);
  const nodes = blocks.map(([key, sig, make]) => {
    const old = kept.get(key);
    if (old && old.sig === sig) return old.node;
    const node = make();
    if (old && old.node.open && node.tagName === "DETAILS") node.open = true;
    kept.set(key, { sig, node });
    return node;
  });
  if (nodes.length === box.children.length && nodes.every((n, i) => box.children[i] === n)) return;  // nothing moved
  const at = nodes.map((n) => n.querySelector(".scroll")?.scrollTop || 0);
  box.replaceChildren(...nodes);
  nodes.forEach((n, i) => { const s = n.querySelector(".scroll"); if (s && at[i]) s.scrollTop = at[i]; });
}

// a painting's number as the painter counts it: its number on their walls, after any hung there at their birth (their
// notebook says "Painting 12" of what the atelier counts as work 10: works set aside never hang)
const no = (w) => w.wall ?? w.number;
const birthCount = (d, a) => (d.artists.find((x) => x.id === a) || {}).walls_at_birth || 0;

// the painting's size and support, as a museum label gives them (ATL-14): "oil on linen, 60 × 37.5 cm"
const cm = (n) => String(n).replace(/\.0$/, "");
const measure = (w) => (w.cm ? `oil on ${w.support === "linen" || !w.support ? "linen" : w.support}, ${cm(w.cm[0])} × ${cm(w.cm[1])} cm` : "");

function label(w) {
  return el("p", { class: "label" },
    el("span", { class: "title", textContent: w.title || "Untitled" }),
    `${studioName(artistOf(w.id))} · painting ${no(w)} · ${MODELS[w.model] || w.model || ""}${w.date ? " · " + day(w.date) : ""}`,
    ...(w.cm ? [el("span", { class: "measure", textContent: measure(w) })] : []));
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
  // the number the painting on the easel will hang under: after what is on their walls
  const next = Math.max(birthCount(d, a), ...works.filter((w) => w.finished).map(no)) + 1;
  if (open) {  // the canvas as they last looked at it, and the way in to watch
    const [state, live] = STATES[open.state] || ["resting", false];
    const watch = `/studio/?p=${encodeURIComponent(open.viewer)}`;
    const look = ls.find((x) => x.p === open.viewer);
    if (look && look.look != null) easel.append(el("a", { href: watch, class: "canvas" }, el("img", { src: `/studio/data/${open.viewer}/v/${look.look}.jpg`, alt: "The painting in progress" })));
    easel.append(el("div", { class: "state" + (live ? " live" : ""), textContent: `On the easel: number ${next}, ${state}` }), " ",
      el("a", { href: watch, textContent: live ? "Watch" : "See it so far", class: "state" }));
  }
  // newest first, wrapping like a hang on a wall; what hung there before their first work comes last
  const done = works.filter((w) => w.finished).sort((x, y) => y.number - x.number);
  const birth = d.artists.find((x) => x.id === a) || {};
  const items = done.map(closeUp);
  const atBirth = [];
  for (let n = birth.walls_at_birth || 0; n >= 1; n--) atBirth.push({ src: `/studio/data/walls-${a}/${n}.jpg`, title: String(n) });
  const all = [...items, ...atBirth];
  // below the walls, folded: what was written. The paintings come first; the words wait until someone asks for them
  const texts = [];
  const last = done[0];
  if (last && last.notebook) texts.push(["notebook", `${last.number}\n${last.notebook}`,
    () => written(`Their notebook, as they left it after painting ${no(last)}`, last.notebook)]);
  if (birth.temperament_note) {  // the owner's note for visitors: a heading line, then paragraphs, set as text (ATL-13)
    const [head, ...rest] = birth.temperament_note.split(/\n/);
    const paras = rest.join("\n").split(/\n\s*\n/).map((x) => x.trim()).filter(Boolean);
    texts.push(["note", birth.temperament_note, () => paras.length
      ? written(head, paras.map((x) => el("p", { textContent: x })))
      : el("p", { class: "state aside", textContent: head })]);
  }
  if (birth.temperament_text) texts.push(["chapter", birth.temperament_text, () => written("The chapter, as placed", birth.temperament_text)]);
  let tbox = document.getElementById("texts");  // a page cached from before it had one: made beside the walls
  if (!tbox) document.getElementById("walls").after(tbox = el("section", { class: "texts", id: "texts", "aria-label": "What was written" }));
  steady(tbox, texts);
  const box = document.getElementById("walls");
  const kids = [];
  if (!all.length) kids.push(el("p", { class: "empty", textContent: "The walls are bare." }));
  const figs = done.map((w, k) => el("figure", {},
    el("img", { src: finalImg(w, true), alt: w.title || "Untitled", loading: "lazy", onclick: () => lightbox(all, k) }),
    el("figcaption", {}, el("a", { href: workHref(w), class: "t", textContent: w.title || "Untitled" }),
      el("div", { class: "state", textContent: `painting ${no(w)}${w.date ? " · " + day(w.date) : ""}${w.cm ? " · " + cm(w.cm[0]) + " × " + cm(w.cm[1]) + " cm" : ""}` }))));
  // a year of paintings stays easy to walk through: the current season on the wall, each earlier one folded under its
  // name (2026-10-13). While everything is from one season, the wall is as it always was.
  const seasons = [];
  done.forEach((w, k) => { const s = season(w.date); if (!seasons.length || seasons.at(-1).name !== s) seasons.push({ name: s, figs: [] }); seasons.at(-1).figs.push(figs[k]); });
  box.classList.toggle("seasons", seasons.length > 1);
  if (seasons.length > 1) {
    seasons.forEach((s, k) => {
      const grid = el("div", { class: "walls" }, ...s.figs);
      const count = `${s.figs.length} ${s.figs.length === 1 ? "painting" : "paintings"}`;
      kids.push(k === 0 ? el("section", { class: "season" }, el("h2", { class: "state", textContent: s.name }), grid)
        : el("details", { class: "season" }, el("summary", { class: "state", textContent: `${s.name} · ${count}` }), grid));
    });
  } else {
    kids.push(...figs);
  }
  if (atBirth.length) {
    const hung = [el("p", { class: "state hung", textContent: birth.walls_note }), ...atBirth.map((it, k) => el("figure", {},
      el("img", { src: it.src, alt: "", loading: "lazy", onclick: () => lightbox(all, items.length + k) }),
      el("figcaption", {}, el("div", { class: "t", textContent: it.title }))))];
    kids.push(...(seasons.length > 1 ? [el("div", { class: "walls" }, ...hung)] : hung));
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
  const img = el("img", { src: finalImg(w), alt: w.title || "Untitled", onclick: () => lightbox([{ ...closeUp(w), href: null }], 0) });
  if (w.px) { img.srcset = srcsetOf(w); img.sizes = "(max-width: 1100px) 100vw, 1068px"; }
  box.append(el("div", { class: "piece" }, img, label(w)));
  box.append(el("p", { class: "actions" }, el("a", { href: `/studio/?p=${encodeURIComponent(w.viewer)}`, textContent: "Watch it being painted" })));
  // short facts stay in sight, quietly; the long texts wait, folded, below
  const facts = el("dl", { class: "facts" });
  if (w.theme) facts.append(el("dt", { textContent: "They were given" }), el("dd", { textContent: w.theme }));
  // a work painted from a box of fewer tubes than all of them (atelier paint --box): said as a theme is
  if (w.box && w.box !== "every") facts.append(el("dt", { textContent: "Their tubes" }),
    el("dd", { textContent: `The ${w.box} box, not all fifty-four. The painter wasn't told its name.` }));
  if (facts.children.length) box.append(facts);
  const texts = el("div", { class: "texts" });
  if (w.reply) texts.append(written("The painter's words", plain(w.reply)));
  if (w.notebook) texts.append(written("Their notebook after this painting", w.notebook));
  if (texts.children.length) box.append(texts);
  // one quiet line, if the owner set this painting above an essay
  for (const e of (await essayList()).filter((x) => x.frontispiece === w.id))
    box.append(el("p", { class: "state frontis" }, "Frontispiece to an essay: ", el("a", { href: essayHref(e), textContent: e.title })));
}

// ---- the owner's essays (/essays/): data/essays.json exists only once one is published; until then the page and its
// link are not on the site at all. Each essay may have a finished work above it, its frontispiece. Set as text, with
// *italics* the only formatting.
async function essayList() {
  try { const r = await fetch("/data/essays.json"); return r.ok ? (await r.json()).essays : []; } catch { return []; }
}
const essayHref = (e) => `/essays/?e=${encodeURIComponent(e.name)}`;
function prose(text) {  // *a few words* in italics; everything else as written
  return text.split(/\*([^*]+)\*/).map((part, k) => (k % 2 ? el("em", { textContent: part }) : part));
}
async function essaysPage() {
  const [list, d] = await Promise.all([essayList(), data()]);
  const box = document.getElementById("essays");
  const name = new URLSearchParams(location.search).get("e");
  const e = name && list.find((x) => x.name === name);
  if (!e) {
    crumbs(["Essays"]);
    box.append(el("h1", { textContent: "Essays" }));
    if (!list.length) box.append(el("p", { class: "empty", textContent: "Nothing here yet." }));
    for (const x of list) box.append(el("p", { class: "essay-item" }, el("a", { href: essayHref(x), textContent: x.title }),
      el("span", { class: "state", textContent: `  ${day(x.published)}` })));
    return;
  }
  document.title = `${e.title} · Atelier`;
  crumbs(["Essays", "/essays/"], [e.title]);
  const w = e.frontispiece && d.works.find((x) => x.id === e.frontispiece && x.finished);
  if (w) box.append(el("figure", { class: "frontispiece" },
    el("a", { href: workHref(w) }, el("img", { src: finalImg(w), alt: w.title || "Untitled" })),
    el("figcaption", { class: "state", textContent: `${w.title || "Untitled"}, ${studioName(artistOf(w.id))}, painting ${no(w)}${w.cm ? ", " + measure(w) : ""}` })));
  box.append(el("h1", { textContent: e.title }), el("p", { class: "state", textContent: day(e.published) }));
  for (const b of e.blocks) box.append(b.h ? el("h2", {}, ...prose(b.h)) : el("p", {}, ...prose(b.p)));
}
// the footer's way in, on every page, once there is something to read
async function essaysLink() {
  const nav = document.querySelector("footer nav");
  if (!nav || nav.querySelector('a[href="/essays/"]') || !(await essayList()).length) return;
  nav.prepend(el("a", { href: "/essays/", textContent: "Essays" }));
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
  essays: essaysPage,
};
pages[document.body.dataset.page]?.();
essaysLink();
