#!/usr/bin/env python3
"""A commission studio's rules (runner/commission.py): the owner's files and their settings, the brief made of them,
the canvas rule for the easel's tools, the queue, and the private flag the export goes by. Nothing paints.

    python3 runner/tests/test_commission.py
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="atelier-commission-"))
os.environ |= {"ATELIER_DATA": str(TMP / "data"), "ATELIER_SECRETS": str(TMP / "secrets"), "ATELIER_WINDOW": "always"}
sys.path.insert(0, str(HERE.parent))
import commission  # noqa: E402
import export  # noqa: E402
import studio  # noqa: E402
from config import DATA, TEXTS  # noqa: E402

failed = 0


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


def refused(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


msgs = json.loads((TEXTS / "messages.json").read_text())
d = commission.folder("iv")
commission.seed("iv")
check("a new studio's folder holds the standing requirements", (d / "standing.md").exists() and (d / "done").is_dir())

c = commission.take("iv")
check("the standing shape is 16:9", c["aspect"] == 1.7778 and c["aspect_words"] == "16:9", c)
check("no commission waiting: a free picture", c["words"] == "" and c["file"] is None)
text = commission.direction(c, msgs)
check("... whose brief is free, in the given shape, with the standing requirements",
      text.startswith(msgs["direction_free"]) and "`aspect=1.7778`" in text and "six inks" in text, text[:300])
check("... and whose easel is held to the shape", commission.canvas_rule(c) == {"aspect": 1.7778, "words": "16:9"})

(d / "b later.md").write_text("## Theme\nRain.\n")
(d / "a first.md").write_text("size: 700\nbox: every\n\n## Theme\nLate light.\n\n## After\nChardin: thick, dry paint.\n")
c = commission.take("iv")
check("the first by name is taken", c["file"] == "a first.md" and c["size"] == 700 and c["box"] == "every", c)
text = commission.direction(c, msgs)
check("its words reach the brief as written", "## Theme\nLate light.\n\n## After\nChardin: thick, dry paint." in text, text[:300])
check("its settings do not", "size: 700" not in text and "box:" not in text)
check("the brief names the given size", "700 mm wide" in text and "`aspect=1.7778` and `size=700`" in text, text)
check("the easel is held to shape and size", commission.canvas_rule(c) == {"aspect": 1.7778, "words": "16:9", "size": 700})
check("the queue is untouched until the work exists", [p.name for p in commission.queue("iv")] == ["a first.md", "b later.md"])
commission.done("iv", c, "iv-001")
check("then the file is kept under the work's id", [p.name for p in commission.queue("iv")] == ["b later.md"]
      and (d / "done" / "iv-001 a first.md").exists())

check("one out of turn, by name", commission.take("iv", name="b later")["file"] == "b later.md")
check("words on the spot", commission.take("iv", "A red door")["words"] == "A red door" and commission.take("iv", "A red door")["file"] is None)
check("an unknown name is refused", "no commission" in (refused(lambda: commission.take("iv", name="nope")) or ""))
(d / "c bad.md").write_text("aspect: wide\n\nA field.\n")
check("a shape that is none is refused", "no canvas shape" in (refused(lambda: commission.take("iv", name="c bad")) or ""))
(d / "c bad.md").write_text("aspect: 4:3\n\nA field.\n")
c = commission.take("iv", name="c bad")
check("a commission's own shape goes before the standing one", c["aspect"] == 1.3333 and "4:3, wider than high" in commission.direction(c, msgs), c)
(d / "c bad.md").write_text("size: 700\n")
check("a commission without words is refused", "no words" in (refused(lambda: commission.take("iv", name="c bad")) or ""))
(d / "direction.md").write_text("## Theme\nBoats.\n")
for f in list(commission.queue("iv")):
    f.rename(f.with_suffix(".held"))
c = commission.take("iv")
check("with nothing waiting, the direction in force is painted", c["file"] == "direction.md" and c["words"] == "## Theme\nBoats." and c["aspect"] == 1.7778, c)
check("... and its brief says it holds for more than this picture", "as for the others painted under it" in commission.direction(c, msgs) and "Boats." in commission.direction(c, msgs))
commission.done("iv", c, "iv-002")
check("... and it stays in force after the work", (d / "direction.md").exists() and commission.take("iv")["file"] == "direction.md")
check("the direction is no commission in the queue", commission.queue("iv") == [] and "no commission" in (refused(lambda: commission.take("iv", name="direction")) or ""))
check("the listing names it", "direction: ## Theme" in commission.listing("iv"), commission.listing("iv"))
for f in d.glob("*.held"):
    f.rename(f.with_suffix(".md"))
check("a commission waiting goes before the direction", commission.take("iv")["file"] == "b later.md" and "kept" not in commission.take("iv"))
(d / "direction.md").unlink()
check("the record keeps the settings, not the words", commission.record(commission.take("iv", name="b later")) ==
      {"file": "b later.md", "aspect": 1.7778, "aspect_words": "16:9"})

# the brief, whole: the template's rule on decisions follows the commission
reg = {"iv": {"root": str(TMP / "root"), "studio_name": "Studio IV", "created": studio.now()},
       "i": {"root": str(TMP / "root-i"), "studio_name": "Studio I", "created": studio.now()}}
studio.save_registry(reg)
for id, birth in (("iv", {"commission": True, "private": True}), ("i", {})):
    (DATA / "artists" / id).mkdir(parents=True)
    (DATA / "artists" / id / "birth.json").write_text(json.dumps(birth))
iv, i = studio.Artist("iv"), studio.Artist("i")
check("the birth record says who takes commissions", iv.commissioned and not i.commissioned)
brief = studio.brief_text(iv, None, commission.take("iv", name="b later"))
check("a commissioned brief", "This picture is a commission." in brief and "Within the commission, every artistic decision is yours." in brief
      and "{" not in brief.replace("canvas{}", ""), brief[:400])
free = studio.brief_text(i, None)
check("a free studio's brief reads as before", "- You make every artistic decision.\n" in free and "The subject and composition are yours." in free
      and "commission" not in free and "{" not in free)
check("a private studio is never exported, with or without a NAS", export.private_artists() == {"iv"}, export.private_artists())

shutil.rmtree(TMP, ignore_errors=True)
print("FAILED" if failed else "all ok")
sys.exit(1 if failed else 0)
