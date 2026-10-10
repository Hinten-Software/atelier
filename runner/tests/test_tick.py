#!/usr/bin/env python3
"""The tick's count of new works (DATA/run/starts-left, the owner 2026-10-10): with 1 left it starts one work and
leaves 0; with 0 it starts none; without the file it starts as before. Nothing paints: the start is recorded only.

    python3 runner/tests/test_tick.py
"""
import argparse, os, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(f"/Users/Shared/atelier/t{os.getpid() % 10000}")
os.environ |= {"ATELIER_DATA": str(DATA), "ATELIER_SECRETS": str(DATA / "secrets"), "ATELIER_WINDOW": "always"}
sys.path.insert(0, str(HERE.parent))
import atelier  # noqa: E402
import budget  # noqa: E402

failed = 0
started = []


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


class FakeArtist:
    def __init__(self, id):
        self.name = f"Studio {id}"

    def works(self):
        return []


def tick():
    started.clear()
    atelier.cmd_tick(argparse.Namespace())
    return list(started)


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    (DATA / "run").mkdir(parents=True)
    atelier.open_work = lambda: None
    atelier.registry = lambda: {"i": {}}
    atelier.Artist = FakeArtist
    atelier.cmd_paint = lambda a: started.append(a.artist)
    budget.spent_today = lambda: 0.0
    try:
        (DATA / "run" / "until").write_text("2099-01-01T00:00:00+00:00\n")
        left = DATA / "run" / "starts-left"
        left.write_text("1\n")
        check("one left: one work starts", tick() == ["i"])
        check("... and none is left", left.read_text().strip() == "0")
        check("none left: nothing starts", tick() == [] and left.read_text().strip() == "0")
        left.unlink()
        check("no count: starts as before", tick() == ["i"] and not left.exists())
        (DATA / "run" / "until").write_text("2000-01-01T00:00:00+00:00\n")
        left.write_text("1\n")
        check("after the standing go: nothing starts, the count is kept", tick() == [] and left.read_text().strip() == "1")
    finally:
        shutil.rmtree(DATA, ignore_errors=True)
    print("all passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
