"""Artists and their studios (requirements ART-1..10, RUN-4, section 7).

An artist's root is /Users/Shared/<r>/ (<r>: two random letters): its studio (the artist's world, its working
directory across all its works) and its Claude Code config. Everything else about the artist (birth record,
notebook and toolkit history, works) is in the private store, DATA/artists/<id>/ and DATA/works/.
"""
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import CLAUDE_VERSION, DATA, EFFORT, MATERIALS, MODEL, NOTES, PAINTER_EASEL, ROOTS, TEXTS

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
NOTEBOOK, TOOLKIT = "notebook.md", "toolkit.lua"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_comments(text: str) -> str:
    """A note as the artist reads it: without HTML comments (the physics note opens with a canary comment)."""
    return re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)


def registry() -> dict:
    p = DATA / "artists.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_registry(reg: dict):
    p = DATA / "artists.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=1))
    tmp.replace(p)


class Artist:
    def __init__(self, id: str):
        reg = registry()
        if id not in reg:
            raise SystemExit(f"no artist {id!r} (artists: {', '.join(reg) or 'none'})")
        self.id, self.rec = id, reg[id]
        self.root = Path(self.rec["root"])
        self.studio = self.root / "studio"
        # ATELIER_CONFIG_DIR: tests only (a config dir that is already logged in), and only with ATELIER_TEST=1, so a
        # variable left in the operator's shell can't give every artist one shared config (QA Q21)
        test_config = os.environ.get("ATELIER_CONFIG_DIR") if os.environ.get("ATELIER_TEST") == "1" else None
        self.config = Path(test_config) if test_config else self.root / ".config"
        self.home = DATA / "artists" / id

    @property
    def name(self) -> str:
        return self.rec["studio_name"]

    def works(self) -> list[Path]:
        return sorted(p for p in (DATA / "works").glob(f"{self.id}-*") if p.is_dir())

    def finished(self) -> list[Path]:
        return [w for w in self.works()
                if (w / "manifest.json").exists() and json.loads((w / "manifest.json").read_text()).get("finished")]


def birth(model: str = MODEL, effort: str = EFFORT) -> Artist:
    """A new artist: a neutral root, an empty studio, its own Claude config, and a public birth record (ART-2)."""
    reg = registry()
    id = ROMAN[len(reg)].lower()
    used = {Path(r["root"]).name for r in reg.values()}
    while True:
        r = "".join(random.choice(string.ascii_lowercase) for _ in range(2))
        if r not in used and not (ROOTS / r).exists():
            break
    root = ROOTS / r
    (root / "studio").mkdir(parents=True)
    (root / ".config").mkdir()
    root.chmod(0o700)
    reg[id] = {"root": str(root), "studio_name": f"Studio {ROMAN[len(reg)]}", "created": now()}
    save_registry(reg)
    a = Artist(id)
    a.home.mkdir(parents=True, exist_ok=True)
    (a.home / "history").mkdir(exist_ok=True)
    (a.home / "birth.json").write_text(json.dumps({
        "id": id, "studio": a.name, "created": reg[id]["created"], "model": model, "effort": effort,
        "claude_code": CLAUDE_VERSION, "founding_statement": None,
    }, indent=1))
    (a.studio / NOTEBOOK).write_text("")
    (a.studio / TOOLKIT).write_text("")
    return a


def brief_text(artist: Artist, theme: str | None) -> str:
    msgs = json.loads((TEXTS / "messages.json").read_text())
    direction = msgs["direction_themed"].replace("{THEME}", theme.strip().rstrip(".")) if theme else msgs["direction_free"]
    notebook = msgs["notebook_later"] if artist.finished() else msgs["notebook_first"]
    return (TEXTS / "brief.md").read_text().replace("{DIRECTION}", direction).replace("{NOTEBOOK}", notebook)


def prepare(artist: Artist, theme: str | None) -> dict:
    """Set the studio up for a new work (RUN-4): the easel, the notes, this work's brief, an empty journal and
    easel. The notebook, toolkit and walls stay as the artist left them. Returns hashes for the manifest."""
    s = artist.studio
    for d in ("bin", "notes/research", "paintings/lua", "walls"):
        (s / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAINTER_EASEL, s / "bin" / "easel")
    for src, dst in NOTES.items():
        (s / "notes" / dst).write_text(strip_comments((MATERIALS / src).read_text()))
    (s / "notes" / "journal.md").write_text("")
    for leftover in (s / "paintings" / "lua").glob("*"):
        leftover.unlink()
    shutil.rmtree(s / "out", ignore_errors=True)
    (s / "BRIEF.md").write_text(brief_text(artist, theme))
    for f in (NOTEBOOK, TOOLKIT):
        (s / f).touch()
    write_walls_index(artist)
    return {"easel": sha256(s / "bin" / "easel"), "brief": sha256(s / "BRIEF.md"),
            "guide": sha256(s / "notes" / "easel_guide.md")}


def write_walls_index(artist: Artist):
    """walls/index.md: the finished works hanging here, oldest first, so the artist can find them (ART-10)."""
    walls = artist.studio / "walls"
    walls.mkdir(parents=True, exist_ok=True)
    cards = sorted(walls.glob("[0-9][0-9][0-9].md"))
    if not cards:
        (walls / "index.md").unlink(missing_ok=True)
        return
    lines = []
    for c in cards:
        title = next((l[2:].strip() for l in c.read_text().splitlines() if l.startswith("# ")), "")
        lines.append(f"- {c.stem}.png{(' · ' + title) if title else ''}")
    (walls / "index.md").write_text("\n".join(lines) + "\n")


def hang(artist: Artist, number: int, image: Path, title: str | None, reply: str):
    """A finished work on the walls: NNN.png (the replay render, 1000 px wide) and NNN.md (title and reply)."""
    walls = artist.studio / "walls"
    walls.mkdir(parents=True, exist_ok=True)
    png = walls / f"{number:03d}.png"
    subprocess.run(["/usr/bin/sips", "--resampleWidth", "1000", str(image), "--out", str(png)], check=True, capture_output=True)
    card = (f"# {title}\n\n" if title else "") + reply.strip() + "\n"
    (walls / f"{number:03d}.md").write_text(card)
    write_walls_index(artist)
