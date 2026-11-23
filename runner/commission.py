"""Commissions: a studio that paints what the owner asks for (the owner, 2026-11-23; Studio IV, for the Frame).

The same easel, engine and runner as every studio. What differs is a few rules:
- the owner's art direction reaches the painter (theme, subject, a painter of the past and their way of working,
  anything), and may speak of composition; Studios I-III stay free between moods (DIR-3);
- the canvas's shape, and its size if the owner says so, is given, and the easel takes no other (bin/canvas, read
  by easel-mcp/src/canvas-rule.ts);
- the owner's standing requirements for every picture of the studio (what it is painted for: for the Frame, six
  inks and what carries on them) are part of the brief;
- the brief is checked for the private words only, not the white room's word list (tools/whiteroom.py), since
  the owner's words may speak of screens, viewers and painters;
- nothing of the studio is exported (export.py private_artists: `private` in its birth record).

The owner writes in DATA/commissions/<studio>/:
    standing.md     for every work of the studio: what its pictures are painted for
    direction.md    the art direction in force: every work is painted under it until the owner changes the file
    <name>.md       one commission each, for one work in place of the direction; the next work takes the first by
                    name and moves it to done/

Each file may open with settings, one a line, then the words the painter reads, as written:
    aspect: 16:9    the canvas's shape, width:height or a number (width / height)
    size: 700       the canvas's width in mm (left out: the painter's choice)
    box: every      the tube box (a commission's only)
A commission's or the direction's settings go before the standing ones. A night with neither is painted free, in
the standing shape and with the standing requirements. The painter's notebook, toolkit and journal are the
studio's and go on from work to work, whatever the direction: what to keep of them is the painter's own.
"""
import json
import re
import shutil
from pathlib import Path

from config import DATA, REPO

DIR = DATA / "commissions"
STANDING = "standing.md"
DIRECTION = "direction.md"
SEED = REPO / "deploy" / "commissions"  # a new studio's standing.md, copied at birth (example.md: one to write from)
SETTINGS = ("aspect", "size", "box")
SETTING = re.compile(rf"^({'|'.join(SETTINGS)})\s*:\s*(.+?)\s*$", re.I)


def folder(studio: str) -> Path:
    return DIR / studio


def parse(text: str) -> tuple[dict, str]:
    """A file's settings (its opening `key: value` lines) and the words after them."""
    lines, meta, i = text.splitlines(), {}, 0
    while i < len(lines):
        if m := SETTING.match(lines[i]):
            meta[m[1].lower()] = m[2]
        elif lines[i].strip():
            break
        i += 1
    return meta, "\n".join(lines[i:]).strip()


def aspect_of(words: str) -> float:
    """"16:9", "16/9" or "1.78": width / height."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:[:/x]\s*(\d+(?:\.\d+)?))?\s*", words)
    if not m or float(m[1]) <= 0 or (m[2] and float(m[2]) <= 0):
        raise SystemExit(f"commission: no canvas shape in aspect: {words!r} (16:9, 4:3 or a number)")
    return float(m[1]) / float(m[2]) if m[2] else float(m[1])


def settings(meta: dict, where: str) -> dict:
    out = {}
    if "aspect" in meta:
        out["aspect"], out["aspect_words"] = round(aspect_of(meta["aspect"]), 4), meta["aspect"].strip()
    if "size" in meta:
        if not re.fullmatch(r"\d+", meta["size"]):
            raise SystemExit(f"commission: {where}: size: {meta['size']!r} is not a whole number of mm")
        out["size"] = int(meta["size"])
    if "size" in out and not 100 <= out["size"] <= 3000:
        raise SystemExit(f"commission: {where}: size: {out['size']} mm (100 to 3000)")
    if "box" in meta:
        out["box"] = meta["box"]
    return out


def queue(studio: str) -> list[Path]:
    """The commissions waiting, first first."""
    return sorted(f for f in folder(studio).glob("*.md") if f.name not in (STANDING, DIRECTION))


def take(studio: str, inline: str | None = None, name: str | None = None) -> dict:
    """The next work's commission: the file named, the words given on the command line, the first one waiting, the
    direction in force, or none (a free picture in the standing shape). Nothing is moved yet: done() does that once the work exists."""
    f = folder(studio) / STANDING
    smeta, standing = parse(f.read_text()) if f.exists() else ({}, "")
    c = settings({k: v for k, v in smeta.items() if k != "box"}, STANDING) | {"standing": standing, "file": None, "words": ""}
    if name:
        path = folder(studio) / (name if name.endswith(".md") else name + ".md")
        if not path.exists() or path.name in (STANDING, DIRECTION):
            raise SystemExit(f"no commission {path.name!r} in {folder(studio)} (waiting: {', '.join(p.name for p in queue(studio)) or 'none'})")
    else:
        path = None if inline else next(iter(queue(studio)), None)
        if not path and not inline and (folder(studio) / DIRECTION).exists() and parse((folder(studio) / DIRECTION).read_text())[1]:
            path, c["kept"] = folder(studio) / DIRECTION, True  # stays where it is, for the works after this one
    if path:
        meta, words = parse(path.read_text())
        if not words:
            raise SystemExit(f"commission: {path.name} holds no words for the painter")
        c |= settings(meta, path.name) | {"file": path.name, "words": words}
    elif inline:
        c["words"] = inline.strip()
    return c


def done(studio: str, c: dict, work: str):
    """The commission's file, once its work exists: out of the queue, kept under the work's id."""
    if c.get("file") and not c.get("kept") and (src := folder(studio) / c["file"]).exists():
        (folder(studio) / "done").mkdir(exist_ok=True)
        shutil.move(src, folder(studio) / "done" / f"{work} {c['file']}")


def canvas_words(c: dict, msgs: dict) -> str:
    """The brief's section on the given canvas ("" if no shape is given)."""
    if "aspect" not in c:
        return ""
    shape = c["aspect_words"] + (", wider than high" if c["aspect"] > 1 else ", higher than wide" if c["aspect"] < 1 else ", square")
    fields = f"`aspect={c['aspect']:g}`"
    if "size" in c:
        shape += f", {c['size']} mm wide"
        fields += f" and `size={c['size']}`"
    return msgs["canvas_given"].replace("{SHAPE}", shape).replace("{FIELDS}", fields)


def direction(c: dict, msgs: dict) -> str:
    """The brief's opening for a commissioned work: what is asked for, the canvas, the standing requirements."""
    opening = msgs["direction_standing" if c.get("kept") else "direction_commission"].replace("{COMMISSION}", c["words"]) if c["words"] else msgs["direction_free"]
    parts = [opening,
             canvas_words(c, msgs), c["standing"]]
    return "\n\n".join(p for p in parts if p)


def canvas_rule(c: dict) -> dict | None:
    """What the easel's tools hold a new canvas to (studio/bin/canvas), or None."""
    if "aspect" not in c:
        return None
    return {"aspect": c["aspect"], "words": c["aspect_words"]} | ({"size": c["size"]} if "size" in c else {})


def record(c: dict) -> dict:
    """What a work's state and manifest keep of its commission (the words themselves are in the brief)."""
    return {k: c[k] for k in ("file", "aspect", "aspect_words", "size") if c.get(k) is not None}


def seed(studio: str):
    """A new commission studio's folder, with the standing requirements to start from."""
    d = folder(studio)
    (d / "done").mkdir(parents=True, exist_ok=True)
    if not (d / STANDING).exists() and (SEED / STANDING).exists():
        shutil.copy2(SEED / STANDING, d / STANDING)


def listing(studio: str) -> str:
    d = folder(studio)
    f = d / STANDING
    meta = settings(parse(f.read_text())[0], STANDING) if f.exists() else {}
    head = f"{d}\nstanding: " + (", ".join(f"{k} {meta[k]}" for k in ("aspect_words", "size") if k in meta) or "no settings")
    words = parse((d / DIRECTION).read_text())[1] if (d / DIRECTION).exists() else ""
    head += "\ndirection: " + (f"{words.splitlines()[0][:80]} ({DIRECTION}, in force until changed)" if words else "none")
    waiting = [f"  {p.name}: {parse(p.read_text())[1].splitlines()[0][:80] if parse(p.read_text())[1] else '(empty)'}" for p in queue(studio)]
    return "\n".join([head, "waiting:" if waiting else "waiting: none (the next work is painted under the direction)" if words else "waiting: none (the next work is free, in the standing shape)", *waiting])


if __name__ == "__main__":
    print(json.dumps(take(__import__("sys").argv[1]), indent=1))
