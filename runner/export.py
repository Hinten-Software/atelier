#!/usr/bin/env python3
"""The public export (requirements REC-3, REC-7, REC-8): DATA/site/, served on the LAN now and by the NAS later.

    python3 runner/export.py

Builds a session farm (DATA/run/farm/w-<work>/, links to each sitting's transcript: finished works' copies in their
packages, the open work's live transcripts), runs claude-paint's static exporter over it, adds data/works.json
(the public fields of each work and the birth records), then scans everything it wrote for private strings. A hit
removes nothing and publishes nothing: the export stops with the reason.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import private_hits  # noqa: E402
from config import DATA, PRIVATE_WORDS, REPO  # noqa: E402

SITE = DATA / "site"            # what is served and pushed: only ever a clean export (QA Q13)
STAGE = DATA / "run" / "stage"  # where the export is built and scanned
BLOCKED = DATA / "run" / "export-blocked.txt"
FARM = DATA / "run" / "farm"
# what may be published (REC-8): the viewer, its data per work (events, looks and their web copies, the painting's
# log), the final renders, works.json
ALLOWED = re.compile(r"^(studio/(index\.html|stream\.css|data/sessions\.json|data/w-[a-z]+-\d{3}/(events\.json|"
                     r"(img|t|v)/\d+\.(png|jpg|webp)|file/paintings/lua/painting\.lua|final\.png|final(-t)?\.jpg)|viewer-\d+\.js|data/walls-[a-z]+/\d+\.jpg))$|^data/works\.json$"
                     # the atelier's own pages (site/ in the repository)
                     r"|^(index\.html|robots\.txt|(about|walls|work|how|studio-room|notes)/index\.html|assets/atelier\.(css|js))$")
NOTES_SETTINGS = DATA / "notes.json"  # {"sitekey": "<the Turnstile widget's public site key>"} (deploy/notes)
PAGES = REPO / "site"
FINAL_WEB = {"final.jpg": 1600, "final-t.jpg": 640}  # the walls' and the door's copies of a finished painting
PUBLIC_MANIFEST = ("id", "studio", "number", "title", "mode", "theme", "start", "end", "model", "effort", "claude_code",
                   "replay_verified", "finished", "contaminated")
CANARY = "35396958-eb10-44fe-8f7d-0720fe551f10"  # public on purpose (README, every page: REC-9)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
IP_RE = re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b")  # 127.x (loopback) names no machine


def farm():
    """Each work's transcripts, in sitting order, as the viewer's per-painter session folders."""
    for old in FARM.glob("w-*/*"):
        old.unlink()
    works = []
    for w in sorted((DATA / "works").glob("*-[0-9][0-9][0-9]")):
        sf = DATA / "run" / w.name / "state.json"
        state = json.loads(sf.read_text()) if sf.exists() else {}
        man = json.loads((w / "manifest.json").read_text()) if (w / "manifest.json").exists() else {}
        if state.get("contaminated") or man.get("contaminated") or (not state and not man):
            continue  # stopped by the white-room audit: private unless the operator releases it (QA Q20)
        works.append(w)
        d = FARM / f"w-{w.name}"
        d.mkdir(parents=True, exist_ok=True)
        for rec in state.get("sittings", []):
            packaged = w / "sessions" / f"{rec['session']}.jsonl"
            src = packaged if packaged.exists() else Path(rec["transcript"])
            if src.exists():
                (d / f"{rec['n']:03d}-{rec['session']}.jsonl").symlink_to(src)
    return works


def works_json(works):
    out = []
    for w in works:
        m = w / "manifest.json"
        state = DATA / "run" / w.name / "state.json"
        if m.exists():
            man = json.loads(m.read_text())
            pub = {k: man.get(k) for k in PUBLIC_MANIFEST}
            pub["reply"] = (w / "reply.md").read_text() if (w / "reply.md").exists() else ""
            # the date of the painting as the atelier's calendar has it (the last sitting's day), not a visitor's
            pub["date"] = (man.get("sittings") or [{}])[-1].get("date_shown")
        elif state.exists():  # the open work
            st = json.loads(state.read_text())
            pub = {"id": w.name, "number": st["number"], "mode": st["mode"], "theme": st["theme"], "start": st["created"],
                   "state": st["state"], "finished": False}
        else:
            continue
        pub["viewer"] = f"w-{w.name}"
        pub["artist"] = w.name.split("-")[0]
        out.append(pub)
    births = [json.loads(p.read_text()) for p in sorted((DATA / "artists").glob("*/birth.json"))]
    return {"works": out, "artists": births}


def externalize_scripts(page: Path):
    """The viewer's inline scripts as files beside it: the site's Content-Security-Policy allows no inline
    script (ATL-13), so a page with one shows nothing. Order and behaviour are kept (classic scripts, in place)."""
    html = page.read_text()
    n = 0

    def out(m):
        nonlocal n
        n += 1
        (page.parent / f"viewer-{n}.js").write_text(m.group(1))
        return f'<script src="viewer-{n}.js"></script>'
    html = re.sub(r"<script>(.*?)</script>", out, html, flags=re.S)
    page.write_text(html)


def web_finals(png: Path, data: Path):
    """JPEG copies of a finished painting for the pages, made once per painting."""
    try:
        from PIL import Image
    except ImportError:
        return
    for name, size in FINAL_WEB.items():
        out = data / name
        if out.exists() and out.stat().st_mtime >= png.stat().st_mtime:
            continue
        im = Image.open(png).convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        im.save(out, "JPEG", quality=86, optimize=True, progressive=True)


def scan(site: Path) -> list[str]:
    hits = []
    for f in site.rglob("*"):
        if any(part.startswith(".") for part in f.relative_to(site).parts):
            continue
        if f.is_file() and f.suffix in (".json", ".html", ".css", ".js", ".md", ".txt", ".lua"):
            text = f.read_text(errors="replace")
            for h in private_hits(text):
                hits.append(f"{f.relative_to(site)}: {h}")
            if "/Users/" in text:
                hits.append(f"{f.relative_to(site)}: a local path")
            for rx, what in ((UUID_RE, "a session id"), (IP_RE, "a local IP")):
                for m in rx.finditer(text):
                    if m.group(0) != CANARY and not text.startswith(".png", m.end()):  # a look's file name
                        hits.append(f"{f.relative_to(site)}: {what} {m.group(0)!r}")
                        break
    return hits


def redact(hit: str) -> str:
    """A hit as the block report gives it: what and where, never the private text itself."""
    return re.sub(r"'[^']*'", "'…'", hit)


def blocked(hits: list[str]) -> int:
    BLOCKED.write_text("\n".join(redact(h) for h in hits) + "\n")
    print("export: private strings in the export (REC-7); the site is left as it was:", *[redact(h) for h in hits[:20]],
          sep="\n  ", file=sys.stderr)
    return 2


def publish():
    """Swap the scanned stage in as the site, without its dot-files (the exporter's file list)."""
    new = DATA / "site.new"
    shutil.rmtree(new, ignore_errors=True)
    shutil.copytree(STAGE, new, ignore=shutil.ignore_patterns(".*"))
    old = DATA / "site.old"
    shutil.rmtree(old, ignore_errors=True)
    if SITE.exists():
        SITE.rename(old)
    new.rename(SITE)
    shutil.rmtree(old, ignore_errors=True)


def main() -> int:
    works = farm()
    STAGE.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(REPO / "viewer" / "export_static.py"), str(STAGE / "studio"),
                        "--sessions", str(FARM), "--private-words", str(PRIVATE_WORDS)], capture_output=True, text=True)
    if r.returncode:  # the exporter stops on a private word: nothing of this run is published
        return blocked([l for l in (r.stdout + r.stderr).splitlines() if l.strip()][-3:])
    SITE_ = STAGE
    externalize_scripts(SITE_ / "studio" / "index.html")
    for w in works:
        data = SITE_ / "studio" / "data" / f"w-{w.name}"
        if not data.exists():
            continue
        log = w / "painting.lua"  # a finished work's painting is its package's log, not the studio's current one
        if log.exists():
            (data / "file" / "paintings" / "lua").mkdir(parents=True, exist_ok=True)
            (data / "file" / "paintings" / "lua" / "painting.lua").write_bytes(log.read_bytes())
        if (w / "final.png").exists():
            shutil.copy2(w / "final.png", data / "final.png")
            web_finals(w / "final.png", data)
        ev = data / "events.json"  # the studio's path names its root on this machine: published as "studio"
        ev.write_text(re.sub(r"/Users/Shared/[a-z0-9]+/studio", "studio", ev.read_text()))
    keep = {f"w-{w.name}" for w in works}
    for stale in (SITE_ / "studio" / "data").glob("w-*"):
        if stale.name not in keep:
            shutil.rmtree(stale)
    for born in sorted((DATA / "artists").glob("*/walls-at-birth")):  # paintings hung before a studio's first work
        dst = SITE_ / "studio" / "data" / f"walls-{born.parent.name}"
        dst.mkdir(parents=True, exist_ok=True)
        for png in born.glob("*.png"):
            out = dst / f"{png.stem}.jpg"
            if not out.exists() or out.stat().st_mtime < png.stat().st_mtime:
                from PIL import Image
                Image.open(png).convert("RGB").save(out, "JPEG", quality=88, optimize=True, progressive=True)
    for f in PAGES.rglob("*"):  # the atelier's own pages, scanned and allowlisted like everything else
        if f.is_file() and not f.name.startswith("."):
            dst = SITE_ / f.relative_to(PAGES)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            if f.suffix == ".html" and NOTES_SETTINGS.exists():  # the bot check's public key, where a note can be left
                key = json.loads(NOTES_SETTINGS.read_text()).get("sitekey", "")
                if re.fullmatch(r"[0-9A-Za-z_-]{10,64}", key):
                    dst.write_text(dst.read_text().replace("TURNSTILE_SITE_KEY", key))
    (SITE_ / "data").mkdir(exist_ok=True)
    (SITE_ / "data" / "works.json").write_text(json.dumps(works_json(works), indent=1))
    hits = scan(SITE_)
    for f in SITE_.rglob("*"):  # REC-8: nothing outside the allowlist (the exporter's own list file stays behind)
        rel = str(f.relative_to(SITE_))
        if f.is_file() and not ALLOWED.match(rel) and not any(part.startswith(".") for part in f.relative_to(SITE_).parts):
            hits.append(f"{rel}: not on the export allowlist")
    if hits:
        return blocked(hits)
    publish()
    BLOCKED.unlink(missing_ok=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "exported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
