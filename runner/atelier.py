#!/usr/bin/env python3
"""The atelier's runner (requirements 5.10). Started by a person (Q1); carries a work through its sittings.

    atelier birth                              a new artist (after the probe suite has passed: RUN-16)
    atelier paint <artist> [--theme TEXT] --by owner|operator
                                               start a work; the runner continues in the background
    atelier status                             the artists, and the open work and its state
    atelier resume [--clear REASON]            continue an interrupted work (a person, after a reboot or a crash);
                                               --clear: continue a work the white-room audit stopped (logged)
    atelier next                               whose turn it is (fewest works)
    atelier export                             export the site now (the runner does every 2 minutes during a work)
    atelier serve [--host H] [--port P]        serve the export on the LAN
    atelier run <work>                         (internal) the runner itself
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CLAUDE, DATA, TOKEN  # noqa: E402
from studio import Artist, birth, registry  # noqa: E402
from works import CURRENT, RUN, TERMINAL, Work, event, log  # noqa: E402


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def open_work() -> Work | None:
    return Work(CURRENT.read_text().strip()) if CURRENT.exists() else None


def runner_alive(w: Work) -> bool:
    """The runner of this work is running: its pid is alive, the machine hasn't restarted since it was recorded, and
    the process is that runner (a pid can be reused after a reboot, QA Q15)."""
    from works import boot_time
    f = w.run / "runner.pid"
    if not f.exists():
        return False
    rec = json.loads(f.read_text())
    if rec.get("boot") != boot_time() or not alive(rec["pid"]):
        return False
    cmd = subprocess.run(["/bin/ps", "-o", "command=", "-p", str(rec["pid"])], capture_output=True, text=True).stdout
    return f"run {w.id}" in cmd


def detach(w: Work):
    """The runner as its own process, so the work goes on when the terminal that started it closes."""
    out = open(w.run / "runner.out", "a")
    subprocess.Popen([sys.executable, __file__, "run", w.id], stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                     start_new_session=True, cwd=str(DATA))
    print(f"{w.id}: the runner is painting with {w.artist.name}; `atelier status` shows how it goes")


def cmd_birth(a):
    from probes import harness_fingerprint
    ok = (DATA / "run" / f"probe-ok-{harness_fingerprint()}.json").exists()
    if not ok and not a.without_probes:
        raise SystemExit("the probe suite hasn't passed for this harness yet (RUN-16): run runner/probes.py first")
    artist = birth()
    event(f"{artist.name} born ({artist.id}), model and effort in its birth record")
    print(f"{artist.name} ({artist.id}) is born")


def cmd_paint(a):
    if not CLAUDE.exists():
        raise SystemExit(f"no pinned Claude Code at {CLAUDE} (RUN-15)")
    w = Work.create(Artist(a.artist), a.theme, a.by)
    detach(w)


def cmd_run(a):
    w = Work(a.work)
    w.go()


def cmd_status(a):
    reg = registry()
    for id in reg:
        art = Artist(id)
        print(f"{art.name} ({id}): {len(art.finished())} finished, {len(art.works())} works")
    import budget
    print(f"today: ${budget.spent_today():.2f} of ${budget.DAILY_USD:.0f}; painting window {budget.WINDOW} "
          f"({'open' if budget.in_window() else 'closed'})")
    w = open_work()
    if not w:
        print("no open work")
        return
    print(f"this work: ${budget.spent_on(w.id):.2f} of ${budget.WORK_USD:.0f}"
          + (f"; studio closed until {w.state.get('closed_until')} ({w.state.get('closed_why')})" if w.state["state"] == "closed" else ""))
    st = w.state["state"]
    if st not in TERMINAL and st != "stopped" and not runner_alive(w):
        st = f"{st} -> interrupted (no runner: `atelier resume` continues it)"
    s = w.state["sittings"]
    print(f"open work {w.id} ({w.artist.name}, {w.state['mode']}): {st}; {len(s)} sittings"
          + (f", last ended {s[-1]['how']}" if s and s[-1].get("how") else ""))
    if w.state.get("hits"):
        print("audit:", *w.state["hits"][:5], sep="\n  ")


def cmd_resume(a):
    w = open_work()
    if not w:
        raise SystemExit("no open work")
    if runner_alive(w):
        raise SystemExit(f"{w.id}: the runner is still going")
    st = w.state["state"]
    if st == "stopped":
        if not a.clear:
            raise SystemExit(f"{w.id} was stopped by the white-room audit; continue with --clear 'reason' (logged)")
        event(f"work {w.id}: operator cleared the audit stop: {a.clear}")
    elif st in TERMINAL:
        raise SystemExit(f"{w.id} is {st}")
    elif st == "finishing":  # the artist had finished: finish it, never a new sitting (QA Q8)
        event(f"work {w.id}: finishing resumed by a person")
        detach(w)
        return
    elif st in ("sitting", "interrupted"):
        last = w.state["sittings"][-1] if w.state["sittings"] else None
        if last and not last.get("how"):  # the sitting the reboot or the runner's death cut off
            last.update(how="interrupted", end=last.get("end") or "unknown")
        w.state["involuntary"] += 1
        event(f"work {w.id} resumed by a person after an interruption")
    w.set("resumed")
    detach(w)


def cmd_serve(a):
    """The export, served on this machine's network (M1: the live view on the LAN)."""
    import functools
    import http.server
    site = DATA / "site"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    print(f"serving {site} on http://{a.host}:{a.port}/studio/")
    http.server.ThreadingHTTPServer((a.host, a.port), handler).serve_forever()


def cmd_export(a):
    from works import export_now
    export_now()


def cmd_next(a):
    reg = registry()
    if not reg:
        raise SystemExit("no artists yet")
    counts = sorted((len(Artist(id).works()), id) for id in reg)
    print(f"{Artist(counts[0][1]).name} ({counts[0][1]}): {counts[0][0]} works so far")


def main():
    p = argparse.ArgumentParser(prog="atelier", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("birth")
    b.add_argument("--without-probes", action="store_true", help=argparse.SUPPRESS)
    pp = sub.add_parser("paint")
    pp.add_argument("artist")
    pp.add_argument("--theme")
    pp.add_argument("--by", required=True, choices=["owner", "operator"])
    r = sub.add_parser("run")
    r.add_argument("work")
    sub.add_parser("status")
    rs = sub.add_parser("resume")
    rs.add_argument("--clear")
    sub.add_parser("next")
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8800)
    sub.add_parser("export")
    a = p.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    DATA.chmod(0o700)
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
