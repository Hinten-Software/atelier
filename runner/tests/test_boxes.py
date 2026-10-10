#!/usr/bin/env python3
"""The boxes a work can be given (tools/build-engine.sh builds a painter's easel per box): each has its easel and its
tube table, the studio's guide shows the work's box's table and no other, and a box that isn't built is refused.

    python3 runner/tests/test_boxes.py      (after tools/build-engine.sh)
"""
import argparse, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ |= {"ATELIER_DATA": f"/Users/Shared/atelier/b{os.getpid() % 10000}", "ATELIER_SECRETS": "/nonexistent"}
sys.path.insert(0, str(HERE.parent))
import atelier  # noqa: E402
import config  # noqa: E402
import studio  # noqa: E402

failed = 0


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


def table(text):
    """The tube table's rows (the guide has other tables too)."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| tube | pigment |"))
    rows = []
    for l in lines[start + 2:]:
        if not l.startswith("|"):
            break
        rows.append(l)
    return rows


boxes = config.boxes()
check("the default box is built", config.DEFAULT_BOX in boxes, boxes)
check("more boxes than the default", len(boxes) > 1, boxes)
for b in boxes:
    rows = table((config.PAINTER_BOXES / b / "tubes.md").read_text())
    guide = studio.guide_for(b)
    check(f"{b}: its guide shows its {len(rows)} tubes", table(guide) == rows and len(rows) > 0)
    check(f"{b}: the guide names no box", "--@ box" not in guide and f'box "{b}"' not in guide)
every = table(studio.guide_for("every"))
check("every holds every other box's tubes", all(set(table(studio.guide_for(b))) <= set(every) for b in boxes))
try:
    atelier.cmd_paint(argparse.Namespace(artist="i", theme=None, by="owner", box="no-such-box"))
    check("an unknown box is refused", False)
except SystemExit as e:
    check("an unknown box is refused", "no box 'no-such-box'" in str(e) or "no pinned Claude" in str(e), e)
print("all passed" if not failed else f"{failed} failed")
sys.exit(1 if failed else 0)
