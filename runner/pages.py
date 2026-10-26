"""The pages as text in the HTML itself, for whoever reads a page without running its script (an assistant fetching it
for a person, a search engine): the door, each studio's walls, each painting, the essays, at addresses of their own
(/walls/i/, /work/i-001/, /essays/<name>/). The script renders the same over it, as it always has. Also the site's map
(sitemap.xml) and its summary for language models (llms.txt). Everything an artist wrote is escaped (ATL-13).

Mirrors site/assets/atelier.js: a change to what a page shows there belongs here too."""
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

SITE_URL = "https://notart.fyi"
ROMAN = {"i": "I", "ii": "II", "iii": "III"}
MODELS = {"claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-fable-5-1": "Claude Fable 5.1"}
STATES = {"sitting": ("painting now", True), "resumed": ("painting now", True), "prepared": ("about to paint", False),
          "between": ("resting between sittings", False), "closed": ("resting", False), "limit-wait": ("resting", False),
          "crash-wait": ("resting", False), "interrupted": ("resting", False), "finishing": ("finishing", False)}
OWN = ("walls", "work", "essays")  # the folders whose subfolders this module writes, each export anew

esc = html.escape


def studio_name(a): return f"Studio {ROMAN.get(a, a.upper())}"
def artist_of(id): return id.split("-")[0]
def no(w): return w.get("wall") or w.get("number")
def plain(s): return re.sub(r"`([^`]+)`", r"\1", re.sub(r"\*\*(.+?)\*\*", r"\1", s or ""))
def cm(n): return re.sub(r"\.0$", "", str(n))
def work_href(w): return f"/work/{w['id']}/"
def walls_href(a): return f"/walls/{a}/"
def essay_href(e): return f"/essays/{e['name']}/"
def final_img(w, small=False): return f"/studio/data/{w['viewer']}/{'final-t.jpg' if small else 'final.jpg'}"


def day(iso):
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%B %Y')}"


def season(iso):
    if not iso:
        return "Undated"
    y, m = int(iso[:4]), int(iso[5:7])
    if m == 12:
        return f"Winter {y}–{str(y + 1)[2:]}"
    if m <= 2:
        return f"Winter {y - 1}–{str(y)[2:]}"
    return f"{'Spring' if m <= 5 else 'Summer' if m <= 8 else 'Autumn'} {y}"


def measure(w):
    if not w.get("cm"):
        return ""
    support = "linen" if w.get("support") in ("linen", None, "") else w["support"]
    return f"oil on {support}, {cm(w['cm'][0])} × {cm(w['cm'][1])} cm"


def written(heading, text="", paras=()):
    """A text in full, folded under a heading, as the script sets it: as written, or as paragraphs."""
    body = "".join(f"<p>{esc(p)}</p>" for p in paras) if paras else f"<pre>{esc(text.strip())}</pre>"
    return (f'<details class="written"><summary>{esc(heading)}</summary>'
            f'<div class="scroll" tabindex="0" aria-label="{esc(heading)}" role="region">{body}</div></details>')


def label(w):
    meta = f"{studio_name(artist_of(w['id']))} · painting {no(w)} · {MODELS.get(w.get('model'), w.get('model') or '')}"
    meta += f" · {day(w.get('date'))}" if w.get("date") else ""
    size = f'<span class="measure">{esc(measure(w))}</span>' if w.get("cm") else ""
    return f'<p class="label"><span class="title">{esc(w.get("title") or "Untitled")}</span>{esc(meta)}{size}</p>'


# ---- the pages


def door(d, looks):
    born = {a["id"]: a for a in d["artists"]}
    cards = []
    for a in ("i", "ii", "iii"):
        works = [w for w in d["works"] if artist_of(w["id"]) == a]
        open_ = next((w for w in works if not w["finished"] and w.get("state")), None)
        done = sorted((w for w in works if w["finished"]), key=lambda w: -(w.get("number") or 0))
        img, state, live = None, "empty", False
        if a in born:
            state, live = STATES.get(open_["state"], ("resting", False)) if open_ else ("idle", False)
            look = open_ and next((s for s in looks if s.get("p") == open_["viewer"]), None)
            if look and look.get("look") is not None:
                img = f"/studio/data/{open_['viewer']}/v/{look['look']}.jpg"
            elif done:
                img = final_img(done[0], True)
            elif born[a].get("walls_at_birth"):
                img = f"/studio/data/walls-{a}/{born[a]['walls_at_birth']}.jpg"
        pic = f'<img src="{img}" alt="" loading="lazy">' if img else "<span>" + ("" if a in born else "empty") + "</span>"
        frame = f'<div class="frame">{pic}</div>'
        inner = f'{frame}<h2>{studio_name(a)}</h2><div class="state{" live" if live else ""}">{state}</div>'
        cards.append(f'<a class="studio" href="{walls_href(a)}">{inner}</a>' if a in born else f'<div class="studio">{inner}</div>')
    return "".join(cards)


def walls(d, looks, a):
    """One studio's walls: what is on the easel, the finished paintings newest first, what was written."""
    birth = next((x for x in d["artists"] if x["id"] == a), {})
    works = [w for w in d["works"] if artist_of(w["id"]) == a]
    open_ = next((w for w in works if not w["finished"] and w.get("state")), None)
    done = sorted((w for w in works if w["finished"]), key=lambda w: -(w.get("number") or 0))
    easel = ""
    if open_:
        state, live = STATES.get(open_["state"], ("resting", False))
        nxt = max([birth.get("walls_at_birth") or 0, *(no(w) for w in done)]) + 1
        watch = f"/studio/?p={open_['viewer']}"
        look = next((s for s in looks if s.get("p") == open_["viewer"]), None)
        if look and look.get("look") is not None:
            easel += f'<a href="{watch}" class="canvas"><img src="/studio/data/{open_["viewer"]}/v/{look["look"]}.jpg" alt="The painting in progress"></a>'
        easel += (f'<div class="state{" live" if live else ""}">On the easel: number {nxt}, {state}</div> '
                  f'<a href="{watch}" class="state">{"Watch" if live else "See it so far"}</a>')
    figs = []
    for w in done:
        line = f"painting {no(w)}" + (f" · {day(w.get('date'))}" if w.get("date") else "") \
            + (f" · {cm(w['cm'][0])} × {cm(w['cm'][1])} cm" if w.get("cm") else "")
        figs.append((season(w.get("date")), f'<figure><img src="{final_img(w, True)}" alt="{esc(w.get("title") or "Untitled")}" loading="lazy">'
                     f'<figcaption><a href="{work_href(w)}" class="t">{esc(w.get("title") or "Untitled")}</a>'
                     f'<div class="state">{esc(line)}</div></figcaption></figure>'))
    seasons = []
    for name, fig in figs:
        if not seasons or seasons[-1][0] != name:
            seasons.append((name, []))
        seasons[-1][1].append(fig)
    at_birth = birth.get("walls_at_birth") or 0
    kids = [] if done or at_birth else ['<p class="empty">The walls are bare.</p>']
    if len(seasons) > 1:
        for k, (name, fs) in enumerate(seasons):
            grid = f'<div class="walls">{"".join(fs)}</div>'
            count = f"{len(fs)} {'painting' if len(fs) == 1 else 'paintings'}"
            kids.append(f'<section class="season"><h2 class="state">{esc(name)}</h2>{grid}</section>' if k == 0 else
                        f'<details class="season"><summary class="state">{esc(name)} · {count}</summary>{grid}</details>')
    else:
        kids += [f for _, f in figs]
    if at_birth:
        hung = [f'<p class="state hung">{esc(birth.get("walls_note") or "")}</p>'] + [
            f'<figure><img src="/studio/data/walls-{a}/{n}.jpg" alt="" loading="lazy"><figcaption><div class="t">{n}</div></figcaption></figure>'
            for n in range(at_birth, 0, -1)]
        kids += [f'<div class="walls">{"".join(hung)}</div>'] if len(seasons) > 1 else hung
    texts = []
    if done and done[0].get("notebook"):
        texts.append(written(f"Their notebook, as they left it after painting {no(done[0])}", done[0]["notebook"]))
    if birth.get("temperament_note"):
        head, *rest = birth["temperament_note"].split("\n")
        paras = [p.strip() for p in re.split(r"\n\s*\n", "\n".join(rest)) if p.strip()]
        texts.append(written(head, paras=paras) if paras else f'<p class="state aside">{esc(head)}</p>')
    if birth.get("temperament_text"):
        texts.append(written("The chapter, as placed", birth["temperament_text"]))
    return {"name": esc(studio_name(a)), "easel": easel, "walls": "".join(kids), "texts": "".join(texts)}


def work(w, essays):
    t = esc(w.get("title") or "Untitled")
    src = f' srcset="{final_img(w)} 1600w, /studio/data/{w["viewer"]}/final-f.jpg {w["px"]}w" sizes="(max-width: 1100px) 100vw, 1068px"' if w.get("px") else ""
    out = f'<div class="piece"><img src="{final_img(w)}" alt="{t}"{src}>{label(w)}</div>'
    out += f'<p class="actions"><a href="/studio/?p={w["viewer"]}">Watch it being painted</a></p>'
    facts = ""
    if w.get("theme"):
        facts += f"<dt>They were given</dt><dd>{esc(w['theme'])}</dd>"
    if w.get("box") and w["box"] != "every":
        facts += f"<dt>Their tubes</dt><dd>The {esc(w['box'])} box, not all fifty-four. The painter wasn't told its name.</dd>"
    if facts:
        out += f'<dl class="facts">{facts}</dl>'
    texts = (written("The painter's words", plain(w["reply"])) if w.get("reply") else "") \
        + (written("Their notebook after this painting", w["notebook"]) if w.get("notebook") else "")
    if texts:
        out += f'<div class="texts">{texts}</div>'
    for e in (e for e in essays if e.get("frontispiece") == w["id"]):
        out += f'<p class="state frontis">Frontispiece to an essay: <a href="{essay_href(e)}">{esc(e["title"])}</a></p>'
    return out


def prose(text):
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", esc(text))


def essay(e, d):
    out = ""
    w = e.get("frontispiece") and next((x for x in d["works"] if x["id"] == e["frontispiece"] and x["finished"]), None)
    if w:
        cap = f"{w.get('title') or 'Untitled'}, {studio_name(artist_of(w['id']))}, painting {no(w)}" + (f", {measure(w)}" if w.get("cm") else "")
        out += (f'<figure class="frontispiece"><a href="{work_href(w)}"><img src="{final_img(w)}" alt="{esc(w.get("title") or "Untitled")}"></a>'
                f'<figcaption class="state">{esc(cap)}</figcaption></figure>')
    out += f'<h1>{esc(e["title"])}</h1><p class="state">{day(e["published"])}</p>'
    return out + "".join(f"<h2>{prose(b['h'])}</h2>" if "h" in b else f"<p>{prose(b['p'])}</p>" for b in e["blocks"])


def essay_list(essays):
    items = "".join(f'<p class="essay-item"><a href="{essay_href(e)}">{esc(e["title"])}</a><span class="state">  {day(e["published"])}</span></p>'
                    for e in essays)
    return "<h1>Essays</h1>" + (items or '<p class="empty">Nothing here yet.</p>')


# ---- setting it into a page


def fill(page: str, id: str, inner: str) -> str:
    """The empty element with this id, filled."""
    rx = re.compile(rf'(<(\w+)\b[^>]*\bid="{id}"[^>]*>)(</\2>)')
    if not rx.search(page):
        raise ValueError(f"no empty #{id} in the page")
    return rx.sub(lambda m: m[1] + inner + m[3], page, count=1)


def dress(page: str, title: str, path: str, crumbs=(), description="") -> str:
    """Its title, its address (canonical), a line about it, and where you are (Atelier / Studio III / the painting)."""
    head = f'<title>{esc(title)}</title>\n<link rel="canonical" href="{SITE_URL}{path}">'
    if description:
        head += f'\n<meta name="description" content="{esc(description)}">'
    page = re.sub(r"<title>.*?</title>", lambda _: head, page, count=1)
    if crumbs:
        steps = "".join(f'<span class="sep">/</span>' + (f'<a href="{href}">{esc(text)}</a>' if href else f"<span>{esc(text)}</span>")
                        for text, href in crumbs)
        page = re.sub(r'<header class="top">.*?</header>', lambda _: f'<header class="top"><a href="/">Atelier</a>{steps}</header>', page, count=1)
    return page


def write(stage: Path, rel: str, text: str):
    (stage / rel).parent.mkdir(parents=True, exist_ok=True)
    (stage / rel).write_text(text)


def build(stage: Path, d: dict, essays: list[dict]):
    """Into the staged site (its pages already copied from site/ and versioned): every page's text, the pages of their
    own, sitemap.xml and llms.txt."""
    for top in OWN:  # the stage is reused: a page of a work since withdrawn goes
        for sub in (stage / top).glob("*/"):
            if sub.is_dir():
                shutil.rmtree(sub)
    looks_file = stage / "studio" / "data" / "sessions.json"
    looks = json.loads(looks_file.read_text()) if looks_file.exists() else []
    finished = sorted((w for w in d["works"] if w["finished"]), key=lambda w: (artist_of(w["id"]), w.get("number") or 0))
    studios = [a for a in ("i", "ii", "iii") if any(x["id"] == a for x in d["artists"])]

    index = stage / "index.html"
    index.write_text(fill(index.read_text(), "studios", door(d, looks)))

    tpl = (stage / "walls" / "index.html").read_text()
    for a in studios:
        page = dress(tpl, f"{studio_name(a)} · Atelier", walls_href(a), [(studio_name(a), None)],
                     f"The walls of {studio_name(a)}: the paintings of an AI painter, newest first.")
        for id, inner in walls(d, looks, a).items():
            page = fill(page, id, inner)
        write(stage, f"walls/{a}/index.html", page)
    links = "".join(f'<p><a href="{walls_href(a)}">{studio_name(a)}</a></p>' for a in studios)  # an old /walls/?s= address
    (stage / "walls" / "index.html").write_text(fill(fill(tpl, "name", "The studios"), "walls", links))

    tpl = (stage / "work" / "index.html").read_text()
    for w in finished:
        a = artist_of(w["id"])
        about = f"{w.get('title') or 'Untitled'}: {studio_name(a)}, painting {no(w)}" + (f", {day(w.get('date'))}" if w.get("date") else "") \
            + (f", {measure(w)}" if w.get("cm") else "") + ". A painting by an AI, in simulated oil paint."
        page = dress(tpl, f"{w.get('title') or 'Untitled'} · Atelier", work_href(w),
                     [(studio_name(a), walls_href(a)), (w.get("title") or "Untitled", None)], about)
        write(stage, f"work/{w['id']}/index.html", fill(page, "work", work(w, essays)))
    links = "".join(f'<p><a href="{work_href(w)}">{esc(w.get("title") or "Untitled")}</a> <span class="state">{studio_name(artist_of(w["id"]))}, '
                    f"painting {no(w)}</span></p>" for w in finished)  # an old /work/?w= address
    (stage / "work" / "index.html").write_text(fill(tpl, "work", links))

    if essays:
        tpl = (stage / "essays" / "index.html").read_text()
        for e in essays:
            page = dress(tpl, f"{e['title']} · Atelier", essay_href(e), [("Essays", "/essays/"), (e["title"], None)])
            write(stage, f"essays/{e['name']}/index.html", fill(page, "essays", essay(e, d)))
        (stage / "essays" / "index.html").write_text(fill(dress(tpl, "Essays · Atelier", "/essays/", [("Essays", None)]), "essays", essay_list(essays)))

    pages = ["/", "/about/", "/notes/", *(walls_href(a) for a in studios), *(["/essays/"] if essays else [])]
    urls = [(p, None) for p in pages] + [(work_href(w), w.get("date")) for w in finished] + [(essay_href(e), e["published"]) for e in essays]
    write(stage, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{esc(SITE_URL + p)}</loc>{f'<lastmod>{m}</lastmod>' if m else ''}</url>\n" for p, m in urls) + "</urlset>\n")
    write(stage, "llms.txt", llms(stage, d, essays, studios, finished))


def llms(stage: Path, d, essays, studios, finished) -> str:
    """The atelier in a page of Markdown (llmstxt.org): what it is, and a link to every page worth reading."""
    about = re.search(r"<h1>About</h1>\s*<p>(.*?)</p>", (stage / "about" / "index.html").read_text(), re.S)
    summary = html.unescape(re.sub(r"<[^>]+>", "", about[1])) if about else ""
    out = ["# Atelier", "", f"> {summary}", "",
           "Not training data: robots.txt turns away the crawlers that train AI, and its Content-Signal says ai-train=no. "
           "Search, and assistants reading a page for a person, are welcome.", "",
           "## Pages", "",
           f"- [About]({SITE_URL}/about/): what the atelier is, and how a sitting goes",
           f"- [Notes]({SITE_URL}/notes/): the visitors' guestbook", ""]
    out += ["## Studios", ""]
    for a in studios:
        works = [w for w in d["works"] if artist_of(w["id"]) == a]
        hung = sum(w["finished"] for w in works)
        open_ = next((w for w in works if not w["finished"] and w.get("state")), None)
        easel = f"; on the easel: {STATES.get(open_['state'], ('resting',))[0]}" if open_ else ""
        out.append(f"- [{studio_name(a)}]({SITE_URL}{walls_href(a)}): {hung} {'painting' if hung == 1 else 'paintings'}{easel}")
    out += ["", "## Paintings", ""]
    for w in finished:
        facts = ", ".join(x for x in (f"{studio_name(artist_of(w['id']))}", f"painting {no(w)}", MODELS.get(w.get("model"), w.get("model") or ""),
                                      day(w.get("date")), measure(w)) if x)
        out.append(f"- [{w.get('title') or 'Untitled'}]({SITE_URL}{work_href(w)}): {facts}")
    if essays:
        out += ["", "## Essays", ""] + [f"- [{e['title']}]({SITE_URL}{essay_href(e)}): {day(e['published'])}" for e in essays]
    out += ["", "## Optional", "",
            f"- [works.json]({SITE_URL}/data/works.json): every work as data, with the painter's words and their notebook", ""]
    return "\n".join(out)
