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
DATA = Path(f"/Users/Shared/atelier/t{os.getpid() % 10000}")  # one folder per run: runs can't break each other (QA Q25)
ENV = os.environ | {"ATELIER_DATA": str(DATA), "ATELIER_CLAUDE": str(HERE / "fake_claude.py"), "ATELIER_WAIT_SCALE": "0.005",
                    "ATELIER_WINDOW": "always", "ATELIER_SECRETS": str(DATA / "secrets")}  # never the owner's token
failed = 0


def atelier(*args, ok=True, env=None):
    r = subprocess.run([sys.executable, str(RUNNER), *args], env=ENV | (env or {}), capture_output=True, text=True)
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
        settled = s["state"] == "closed" or not (pid.exists() and _alive(json.loads(pid.read_text())["pid"]))
        if s["state"] in until and settled:  # a closed studio's runner waits on purpose
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
        check("studio starts with an empty notebook and toolkit", (root / "studio/notebook").read_text() == "")

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
        check("walls list names it", "1 Test Study" in (walls / "list").read_text() and (walls / "1 Test Study").exists())
        check("package has the painting, journal, transcripts, final",
              all((DATA / "works/i-001" / f).exists() for f in ("painting.lua", "journal.md", "final.png", "brief.md", "sessions")))
        check("no open work afterwards", "no open work" in atelier("status"))

        # 2. the second work: the brief points to the walls; a leak mid-sitting stops it and rolls the notebook back
        (root / "studio/notebook").write_text("the artist's own note\n")
        modes(root, "notebook", "voluntary")
        atelier("paint", "i", "--by", "operator", "--theme", "A quiet morning")
        s = wait("i-002")
        brief = (root / "studio/brief").read_text()
        check("second brief mentions the walls", "The walls hold finished paintings; walls/list names them." in brief)
        check("themed brief", "A quiet morning. Within it, everything is yours to decide." in brief)
        check("leak stops the sitting", s["state"] == "stopped" and s["sittings"][-1]["how"] == "audit", s["state"])
        check("the hit names the reminder", any("silent_turn_reminder" in h for h in s["hits"]), s["hits"])
        check("notebook rolled back", (root / "studio/notebook").read_text() == "the artist's own note\n")
        out = atelier("resume", ok=False)
        check("resume refuses without --clear", "--clear" in out, out)
        atelier("resume", "--clear", "test: fake leak")
        s = wait("i-002")
        check("cleared work ends, contaminated, not hung", s["state"] == "not-finished", s["state"])
        check("contaminated work not on the walls", not any(walls.glob("2*")))
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
        # 5. a tool result the easel never sent (a harness notice) stops the sitting (QA Q3, Q7)
        modes(root, "injected")
        atelier("paint", "i", "--by", "operator")
        s = wait("i-004")
        check("an injected tool result stops it", s["state"] == "stopped" and any("didn't send" in h for h in s["hits"]), s["hits"])
        atelier("resume", "--clear", "test: injected")
        modes(root, "voluntary")
        wait("i-004")

        # 6. finishing fails midway; resume finishes it without a new sitting (QA Q8)
        modes(root, "voluntary")
        hist = DATA / "artists/i/history"
        shutil.rmtree(hist)
        hist.write_text("not a folder")  # finish() can't write the history copies
        atelier("paint", "i", "--by", "operator")
        s = wait("i-005", until=("finishing",), timeout=120)
        time.sleep(3)
        hist.unlink()
        n_before = len(s["sittings"])
        atelier("resume")
        s = wait("i-005")
        check("resumed finishing adds no sitting", len(s["sittings"]) == n_before, [x["how"] for x in s["sittings"]])
        check("and finishes", s["state"] == "finished", s["state"])

        # 7. kill -9 of the runner leaves Claude Code running; resume stops it first (QA Q9)
        modes(root, "hang", "voluntary")
        atelier("paint", "i", "--by", "operator")
        time.sleep(4)
        st = state("i-006")
        runner = json.loads((DATA / "run/i-006/runner.pid").read_text())["pid"]
        os.kill(runner, 9)
        pgid = st["sittings"][-1]["pgid"]
        check("the orphan is still running", _alive(pgid))
        atelier("resume")
        time.sleep(3)
        check("resume stopped the orphan", not _alive(pgid))
        wait("i-006")

        # 9. guardrails (the owner, 2026-10-05): window, daily budget, work ceiling
        def stop_runner(work):
            pidf = DATA / "run" / work / "runner.pid"
            if pidf.exists():
                os.kill(json.loads(pidf.read_text())["pid"], 9)
            st = state(work)
            if st["sittings"] and st["sittings"][-1].get("pgid") and _alive(st["sittings"][-1]["pgid"]):
                os.killpg(st["sittings"][-1]["pgid"], 9)
            (DATA / "run/current").unlink(missing_ok=True)
        h = time.localtime().tm_hour
        closed_window = f"{(h + 2) % 24}-{(h + 3) % 24}"
        modes(root, "voluntary")
        atelier("paint", "i", "--by", "operator", env={"ATELIER_WINDOW": closed_window})
        s = wait("i-007", until=("closed",), timeout=60)
        check("outside the window the studio stays closed", s["state"] == "closed" and not s["sittings"]
              and s["closed_why"] == "window", s)
        st = atelier("status", env={"ATELIER_WINDOW": closed_window})
        check("status says closed and why", "studio closed until" in st and "(window)" in st, st)
        stop_runner("i-007")

        modes(root, "hang")
        spent = sum(json.loads((DATA / "run/ledger.json").read_text())["days"].values())
        atelier("paint", "i", "--by", "operator", env={"ATELIER_DAILY_USD": f"{spent + 0.02:.4f}"})
        s = wait("i-008", until=("closed",), timeout=120)
        check("today's budget ends the sitting at a safe point", s["sittings"] and s["sittings"][-1]["how"] == "closed (daily)", s["sittings"])
        check("and it isn't counted as involuntary", s["involuntary"] == 0, s["involuntary"])
        led = json.loads((DATA / "run/ledger.json").read_text())
        check("the ledger booked the sitting", led["works"].get("i-008", 0) > 0, led)
        stop_runner("i-008")

        modes(root, "hang")
        atelier("paint", "i", "--by", "operator", env={"ATELIER_WORK_USD": "0.02"})
        s = wait("i-009", timeout=120)
        check("the work ceiling ends the work", s["state"] == "not-finished" and "ceiling" in s.get("why", ""), s.get("why"))

        # 8. limit reset times (QA Q10)
        sys.path.insert(0, str(HERE.parent))
        os.environ["ATELIER_DATA"] = str(DATA)
        os.environ["ATELIER_SECRETS"] = str(DATA / "secrets")
        from datetime import datetime
        import works
        ref = datetime(2026, 10, 3, 13, 55)  # a Saturday
        check("'resets 1pm' read at 13:55 means now", works.reset_time("resets 1pm", ref) - ref.timestamp() < 120)
        check("'resets Sat 1pm' read at 13:55 means now", works.reset_time("resets Sat 1pm", ref) - ref.timestamp() < 120)
        check("'resets 9am' read at 13:55 is tomorrow", 18 * 3600 < works.reset_time("resets 9am", ref) - ref.timestamp() < 20 * 3600)
        check("'resets Mon 9am' is Monday", 1.7 * 86400 < works.reset_time("resets Mon 9am", ref) - ref.timestamp() < 1.9 * 86400)
        check("a 429 is not a usage limit", not works.is_limit("429 rate_limit_error"))
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
