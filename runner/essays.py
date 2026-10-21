#!/usr/bin/env python3
"""The owner's essays (2026-10-13): written in DATA/essays/, shown on the site only once published.

    python3 runner/essays.py              what is there, published or not
    python3 runner/essays.py preview NAME  the essay as it will read, in the browser, before it is published

An essay is a plain text file, DATA/essays/<name>.md:

    # The title
    frontispiece: iii-008
    published: 2026-10-20

    The first paragraph. Paragraphs are separated by an empty line.

    ## A heading inside the essay, if one is wanted

    *A few words in italics* are kept; nothing else is formatting.

`frontispiece` is the finished work shown above the essay (optional). Without a `published` line the essay is a draft:
nothing of it leaves this machine. The Essays page and its footer link exist on the site only once one essay is
published. The essays live here, outside every studio: no painter ever reads them (the white room holds for the
owner's words too).
"""
import html
import re
import sys
import webbrowser
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, REPO  # noqa: E402

ESSAYS = DATA / "essays"
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # its address on the site: /essays/?e=<name>


def parse(path: Path) -> dict:
    lines = path.read_text().splitlines()
    head, i = {}, 0
    if lines and lines[0].startswith("# "):
        head["title"], i = lines[0][2:].strip(), 1
    while i < len(lines) and (m := re.match(r"^(frontispiece|published):\s*(.*)$", lines[i].strip())):
        head[m.group(1)] = m.group(2).strip()
        i += 1
    blocks = []
    for para in re.split(r"\n\s*\n", "\n".join(lines[i:]).strip()):
        para = " ".join(l.strip() for l in para.splitlines()).strip()
        if para:
            blocks.append({"h": para[3:].strip()} if para.startswith("## ") else {"p": para})
    pub = head.get("published")
    return {"name": path.stem, "title": head.get("title") or path.stem, "frontispiece": head.get("frontispiece") or None,
            "published": pub if pub and re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub) and pub <= date.today().isoformat() else None,
            "blocks": blocks}


def all_essays() -> list[dict]:
    if not ESSAYS.is_dir():
        return []
    return [parse(p) for p in sorted(ESSAYS.glob("*.md")) if NAME.match(p.stem)]


def published() -> list[dict]:
    """What the site shows: published essays, newest first."""
    return sorted((e for e in all_essays() if e["published"]), key=lambda e: e["published"], reverse=True)


def preview(name: str):
    """The essay as the site will set it, in a file on this machine only, with the site's own styles."""
    e = parse(ESSAYS / f"{name}.md")
    css = (REPO / "site" / "assets" / "atelier.css").read_text()
    inline = lambda t: re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html.escape(t))
    body = "".join(f"<h2>{inline(b['h'])}</h2>" if "h" in b else f"<p>{inline(b['p'])}</p>" for b in e["blocks"])
    front = ""
    if e["frontispiece"]:
        img = DATA / "site" / "studio" / "data" / f"w-{e['frontispiece']}" / "final.jpg"
        front = f'<figure class="frontispiece"><img src="{img.as_uri()}" alt=""></figure>' if img.exists() else \
            f'<p class="state">(no finished work {html.escape(e["frontispiece"])} on the site)</p>'
    out = DATA / "run" / "essay-preview.html"
    out.write_text(f"<!doctype html><meta charset=utf-8><title>{html.escape(e['title'])} (preview)</title><style>{css}</style>"
                   f"<body><main><article class='prose narrow essay'>{front}<h1>{html.escape(e['title'])}</h1>"
                   f"<p class='state'>{'published ' + e['published'] if e['published'] else 'draft: not on the site'}</p>"
                   f"{body}</article></main></body>")
    webbrowser.open(out.as_uri())
    print(out)


def main():
    if sys.argv[1:2] == ["preview"] and len(sys.argv) == 3:
        return preview(sys.argv[2])
    es = all_essays()
    if not es:
        print(f"no essays yet: write one as {ESSAYS}/<name>.md (see python3 runner/essays.py --help)")
    for e in es:
        print(f"{e['name']}: {e['title']} ({'published ' + e['published'] if e['published'] else 'draft'}"
              f"{', frontispiece ' + e['frontispiece'] if e['frontispiece'] else ''})")
    if "--help" in sys.argv:
        print(__doc__)


if __name__ == "__main__":
    main()
