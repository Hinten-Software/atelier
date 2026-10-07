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
NOTEBOOK, TOOLKIT, JOURNAL, BRIEF = "notebook", "toolkit", "journal", "brief"
# the files of earlier studios (before 2026-10-06), for the package names
PACKAGE_NAMES = {NOTEBOOK: "notebook.md", TOOLKIT: "toolkit.lua", JOURNAL: "journal.md", BRIEF: "brief.md"}


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


def birth(model: str = MODEL, effort: str = EFFORT, studio: str | None = None, walls: Path | None = None,
          temperament: str | None = None) -> Artist:
    """A new artist: a neutral root, an empty studio, its own Claude config, and a public birth record (ART-2).
    studio: which studio ("iii"); default the first one not yet born. walls: a folder of paintings to hang before the
    artist first wakes (named 1, 2, ...: the walls' standard), without cards; the painter is told nothing of them.
    temperament: the owner's text, the notebook's first page at birth, unsigned; the painter is told nothing of it
    and may keep, revise or outgrow it. The text is kept privately (DATA/artists/<id>/temperament-at-birth); the
    public record says only that it was given."""
    reg = registry()
    id = (studio or next(r.lower() for r in ROMAN if r.lower() not in reg)).lower()
    if id in reg or id.upper() not in ROMAN:
        raise SystemExit(f"studio {id!r} can't be born (born already: {', '.join(reg) or 'none'})")
    used = {Path(r["root"]).name for r in reg.values()}
    while True:
        r = "".join(random.choice(string.ascii_lowercase) for _ in range(2))
        if r not in used and not (ROOTS / r).exists():
            break
    root = ROOTS / r
    (root / "studio").mkdir(parents=True)
    (root / ".config").mkdir()
    root.chmod(0o700)
    reg[id] = {"root": str(root), "studio_name": f"Studio {id.upper()}", "created": now()}
    save_registry(reg)
    a = Artist(id)
    a.home.mkdir(parents=True, exist_ok=True)
    (a.home / "history").mkdir(exist_ok=True)
    (a.home / "birth.json").write_text(json.dumps({
        "id": id, "studio": a.name, "created": reg[id]["created"], "model": model, "effort": effort,
        "claude_code": CLAUDE_VERSION, "founding_statement": None,
        "walls_at_birth": len(wall_files(walls)) if walls else 0,
        "walls_note": WALLS_NOTE if walls else None,
        "temperament_note": TEMPERAMENT_NOTE if temperament else None,
    }, indent=1))
    first_page = temperament.strip() + "\n" if temperament else ""
    if temperament:
        (a.home / "temperament-at-birth").write_text(first_page)
    (a.studio / NOTEBOOK).write_text(first_page)
    (a.studio / TOOLKIT).write_text("")
    if walls:
        hang_at_birth(a, walls)
    return a


# what visitors read beside paintings hung before a studio's first work (the owner, 2026-10-06); the painter never
WALLS_NOTE = "The owner of the atelier pre-hung art recreated from their recollection in this studio."
# and beside a studio whose painter was given a temperament at birth, as the first page of their notebook (2026-10-07)
TEMPERAMENT_NOTE = "The owner of the atelier gave this painter a temperament at birth: the first page of their notebook."


def wall_files(folder: Path) -> list[Path]:
    """The paintings to hang, in the order of their names (1, 2, ...)."""
    files = [f for f in folder.iterdir() if f.is_file() and re.fullmatch(r"\d+", f.name)]
    return sorted(files, key=lambda f: int(f.name))


def hang_at_birth(artist: Artist, folder: Path):
    """Paintings on the walls before the painter first wakes: as their own would hang (1000 px, by number), with an
    empty card. Kept also in the private store (DATA/artists/<id>/walls-at-birth/) for the site and backups."""
    walls = artist.studio / "walls"
    walls.mkdir(parents=True, exist_ok=True)
    keep = artist.home / "walls-at-birth"
    keep.mkdir(parents=True, exist_ok=True)
    cards = artist.home / "walls"
    cards.mkdir(parents=True, exist_ok=True)
    for n, f in enumerate(wall_files(folder), 1):
        data = f.read_bytes()
        (walls / str(n)).write_bytes(data)  # bytes only: no file attributes travel with them
        (keep / f"{n}.png").write_bytes(data)
        (cards / f"{n:03d}.json").write_text(json.dumps({"number": n, "title": None, "name": str(n), "words": "",
                                                         "at_birth": True}, indent=1))
    write_walls_list(artist)


def next_wall_number(artist: Artist) -> int:
    """The number the next finished painting hangs under: after everything on the walls, hung at birth or since."""
    return len(list((artist.home / "walls").glob("*.json"))) + 1


def brief_text(artist: Artist, theme: str | None) -> str:
    msgs = json.loads((TEXTS / "messages.json").read_text())
    direction = msgs["direction_themed"].replace("{THEME}", theme.strip().rstrip(".")) if theme else msgs["direction_free"]
    # the walls are mentioned once anything hangs there, painted here or hung at birth, in words that claim neither
    notebook = msgs["notebook_later"] if any((artist.home / "walls").glob("*.json")) else msgs["notebook_first"]
    return (TEXTS / "brief.md").read_text().replace("{DIRECTION}", direction).replace("{NOTEBOOK}", notebook)


def prepare(artist: Artist, theme: str | None) -> dict:
    """Set the studio up for a new work (RUN-4): the easel, the two texts, this work's brief, an empty journal and
    easel. The notebook, toolkit and walls stay as the artist left them. Returns hashes for the manifest.
    The studio names things as a painter would: brief, notebook, toolkit, journal, easel guide, notes on oil paint,
    walls/ (list, and each painting by its number and title). The easel's record of the painting
    (paintings/lua/painting.lua) is out of the painter's reach; its `log` tool shows it."""
    s = artist.studio
    for d in ("bin", "paintings/lua", "walls"):
        (s / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAINTER_EASEL, s / "bin" / "easel")
    for src, dst in NOTES.items():
        (s / dst).write_text(strip_comments((MATERIALS / src).read_text()))
    (s / JOURNAL).write_text("")
    for leftover in (s / "paintings" / "lua").glob("*"):
        leftover.unlink()
    shutil.rmtree(s / "out", ignore_errors=True)
    (s / BRIEF).write_text(brief_text(artist, theme))
    for f in (NOTEBOOK, TOOLKIT):
        (s / f).touch()
    write_walls_list(artist)
    return {"easel": sha256(s / "bin" / "easel"), "brief": sha256(s / BRIEF), "guide": sha256(s / NOTES["easel_guide.md"])}


def wall_name(number: int, title: str | None) -> str:
    """A painting on the walls by its number and title, as a painter would label it: "1 Low Water, Evening"."""
    t = re.sub(r"[/\\:\x00-\x1f]", " ", title or "").strip(" .")
    return f"{number} {t}" if t else str(number)


def write_walls_list(artist: Artist):
    """walls/list: the finished works hanging here, oldest first, each with what the artist said of it (ART-10).
    Made from the cards kept in the private store (DATA/artists/<id>/walls/)."""
    walls = artist.studio / "walls"
    walls.mkdir(parents=True, exist_ok=True)
    cards = sorted((artist.home / "walls").glob("*.json"))
    if not cards:
        (walls / "list").unlink(missing_ok=True)
        return
    parts = []
    for c in cards:
        card = json.loads(c.read_text())
        parts.append(card["name"] + ("\n\n" + card["words"].strip() if card["words"].strip() else ""))
    (walls / "list").write_text("\n\n\n".join(parts) + "\n")


def hang(artist: Artist, number: int, image: Path, title: str | None, reply: str):
    """A finished work on the walls: the replay render, 1000 px wide, named by its number and title, and its card
    (title and the artist's closing words) in the private store, from which walls/list is written."""
    walls = artist.studio / "walls"
    walls.mkdir(parents=True, exist_ok=True)
    name = wall_name(number, title)
    tmp = walls / f".{number}.png"
    subprocess.run(["/usr/bin/sips", "--resampleWidth", "1000", str(image), "--out", str(tmp)], check=True, capture_output=True)
    tmp.rename(walls / name)
    cards = artist.home / "walls"
    cards.mkdir(parents=True, exist_ok=True)
    (cards / f"{number:03d}.json").write_text(json.dumps({"number": number, "title": title, "name": name, "words": reply.strip()}, indent=1))
    write_walls_list(artist)
