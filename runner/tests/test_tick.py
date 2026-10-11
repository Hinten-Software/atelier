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
        # the studios opened for the run: any hour, no daily cap; once the count is used up and nothing is open,
        # the night window and the cap again
        budget.WINDOW = "23-7"
        opened = DATA / "run" / "open"
        opened.touch()
        check("open: any hour, no daily cap", budget.window() == "always" and budget.daily_cap() == float("inf"))
        left.write_text("0\n")
        check("run done: nothing starts, the night window and the cap again", tick() == [] and not opened.exists()
              and budget.window() == "23-7" and budget.daily_cap() == budget.DAILY_USD, budget.window())
        budget.WINDOW = "always"
        (DATA / "run" / "until").write_text("2000-01-01T00:00:00+00:00\n")
        opened.touch()
        check("the go ended: the studios are closed again", tick() == [] and not opened.exists())
        left.write_text("1\n")
        check("after the standing go: nothing starts, the count is kept", tick() == [] and left.read_text().strip() == "1")
        left.unlink()
        (DATA / "run" / "until").write_text("2099-01-01T00:00:00+00:00\n")
        # a work the audit stopped (not Claude's classifier): in the window it is set aside so the night goes on,
        # outside it waits for a person (the owner, 2026-10-11)
        stopped = type("W", (), {"id": "ii-007", "state": {"state": "stopped", "hits": ["attachment 'date' differs"]}})()
        withdrawn = []
        atelier.open_work = lambda: stopped
        atelier.runner_alive = lambda w: False
        atelier.classifier_misfire = lambda w: False
        atelier.cmd_withdraw = lambda a: withdrawn.append(a.why)
        budget.WINDOW = "always"
        check("a stop in the window is set aside", tick() == [] and len(withdrawn) == 1
              and withdrawn[0].startswith("auto: set aside") and "date" in withdrawn[0], withdrawn)
        budget.in_window = lambda: False
        withdrawn.clear()
        check("a stop outside the window waits for a person", tick() == [] and not withdrawn)
        # a failed export is tried again by the tick
        exported = []
        atelier.export_now = lambda: exported.append(1)
        (DATA / "run" / "export-failed").write_text("x\n")
        tick()
        check("a failed export is tried again", exported == [1])
        (DATA / "run" / "export-failed").unlink()
        tick()
        check("... and not when the last one went well", exported == [1])
    finally:
        shutil.rmtree(DATA, ignore_errors=True)
    print("all passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
