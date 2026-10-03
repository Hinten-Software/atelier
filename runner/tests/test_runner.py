#!/usr/bin/env python3
"""The runner's state machine against tests/fake_claude.py and the real easel (requirements 5.10, NFR-10, ART-10).

    python3 runner/tests/test_runner.py

Uses a throwaway private store and throwaway artist roots under /Users/Shared, removed afterwards.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE.parent / "atelier.py"
DATA = Path("/Users/Shared/atelier/t-data")
ENV = os.environ | {"ATELIER_DATA": str(DATA), "ATELIER_CLAUDE": str(HERE / "fake_claude.py"), "ATELIER_WAIT_SCALE": "0.005"}
failed = 0


def atelier(*args, ok=True):
    r = subprocess.run([sys.executable, str(RUNNER), *args], env=ENV, capture_output=True, text=True)
    if ok and r.returncode:
        raise SystemExit(f"atelier {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return r.stdout + r.stderr


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


def state(work):
    return json.loads((DATA / "run" / work / "state.json").read_text())


def wait(work, until=("finished", "not-finished", "stopped"), timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = state(work)
        pid = DATA / "run" / work / "runner.pid"
        if s["state"] in until and not (pid.exists() and _alive(int(pid.read_text()))):
            return s
        time.sleep(1)
    raise SystemExit(f"{work} stuck in {state(work)['state']}")


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def modes(artist_root, *ms):
    cfg = Path(artist_root) / ".config"
    cfg.mkdir(exist_ok=True)
    (cfg / "fake-modes").write_text("\n".join(ms))


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    roots = []
    try:
        atelier("birth", "--without-probes")
        reg = json.loads((DATA / "artists.json").read_text())
        root = Path(reg["i"]["root"])
        roots.append(root)
        check("artist root is neutral", root.parent == Path("/Users/Shared") and len(root.name) == 2, root)
        check("studio starts with an empty notebook and toolkit", (root / "studio/notebook.md").read_text() == "")

        # 1. every kind of end, then the artist stops
        modes(root, "crash", "limit", "context", "voluntary")
        atelier("paint", "i", "--by", "operator")
        s = wait("i-001")
        how = [x["how"] for x in s["sittings"]]
        check("sittings end as crash, limit, context, voluntary", how == ["crash", "limit", "context", "voluntary"], how)
        check("the work is finished", s["state"] == "finished", s["state"])
        m = json.loads((DATA / "works/i-001/manifest.json").read_text())
        check("replay verified", m["replay_verified"], m["replay"])
        check("title from the reply", m["title"] == "Test Study", m["title"])
        check("date shown is recorded", all(x["date_shown"] for x in m["sittings"]), m["sittings"])
        walls = root / "studio/walls"
        check("hung on the walls", (walls / "001.png").exists() and (walls / "001.md").exists(), list(walls.glob("*")))
        check("walls index lists it", "001.png · Test Study" in (walls / "index.md").read_text())
        check("package has the painting, journal, transcripts, final",
              all((DATA / "works/i-001" / f).exists() for f in ("painting.lua", "journal.md", "final.png", "brief.md", "sessions")))
        check("no open work afterwards", "no open work" in atelier("status"))

        # 2. the second work: the brief points to the walls; a leak mid-sitting stops it and rolls the notebook back
        (root / "studio/notebook.md").write_text("the artist's own note\n")
        modes(root, "notebook", "voluntary")
        atelier("paint", "i", "--by", "operator", "--theme", "A quiet morning")
        s = wait("i-002")
        brief = (root / "studio/BRIEF.md").read_text()
        check("second brief mentions walls/", "walls/ holds the paintings you have finished here." in brief)
        check("themed brief", "A quiet morning. Within it, everything is yours to decide." in brief)
        check("leak stops the sitting", s["state"] == "stopped" and s["sittings"][-1]["how"] == "audit", s["state"])
        check("the hit names the reminder", any("silent_turn_reminder" in h for h in s["hits"]), s["hits"])
        check("notebook rolled back", (root / "studio/notebook.md").read_text() == "the artist's own note\n")
        out = atelier("resume", ok=False)
        check("resume refuses without --clear", "--clear" in out, out)
        atelier("resume", "--clear", "test: fake leak")
        s = wait("i-002")
        check("cleared work ends, contaminated, not hung", s["state"] == "not-finished", s["state"])
        check("contaminated work not on the walls", not (walls / "002.png").exists())
        hist = (DATA / "history.md").read_text()
        check("history logs start, audit stop and clearing", "stopped by the white-room audit" in hist and "cleared" in hist)

        # 3. an email in a tool result stops it
        modes(root, "email")
        atelier("paint", "i", "--by", "owner")
        s = wait("i-003")
        check("email in a tool result stops it", s["state"] == "stopped" and any("email" in h for h in s["hits"]), s["hits"])

        # 4. a runner that dies mid-sitting: status says interrupted; a person resumes
        (DATA / "run/current").write_text("i-003")
        s = state("i-003")
        s["state"] = "sitting"
        s["sittings"][-1].update(how=None, end=None)  # as a reboot leaves it: the sitting never ended
        (DATA / "run/i-003/state.json").write_text(json.dumps(s))
        st = atelier("status")
        check("status names the interruption", "interrupted" in st, st)
        modes(root, "voluntary")
        atelier("resume")
        s = wait("i-003")
        check("resumed work ends", s["state"] in ("finished", "not-finished"), s["state"])
        check("the cut-off sitting is recorded as interrupted", s["sittings"][0]["how"] == "interrupted", s["sittings"][0])
    finally:
        if os.environ.get("KEEP"):
            print(f"kept {DATA} and {roots}")
            return
        for r in roots:
            subprocess.run(["/bin/sh", "-c", f"cd {r}/studio && PATH=/usr/bin:/bin bin/easel close"], capture_output=True)
            shutil.rmtree(r, ignore_errors=True)
        shutil.rmtree(DATA, ignore_errors=True)
    print("all passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
