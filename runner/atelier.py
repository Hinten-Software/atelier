#!/usr/bin/env python3
"""The atelier's runner (requirements 5.10). Started by a person (Q1); carries a work through its sittings.

    atelier birth                              a new artist (after the probe suite has passed: RUN-16)
    atelier paint <artist> [--theme TEXT] --by owner|operator
                                               start a work; the runner continues in the background
    atelier status                             the artists, and the open work and its state
    atelier resume [--clear REASON]            continue an interrupted work (a person, after a reboot or a crash);
                                               --clear: continue a work the white-room audit stopped (logged)
    atelier next                               whose turn it is (fewest works)
    atelier withdraw --why TEXT                end the open work stopped by the audit as not finished, private (logged)
    atelier tick                               (launchd, every 10 minutes) the owner's standing go: resume or start
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
from config import CLAUDE, DATA, REPO, TOKEN  # noqa: E402
from studio import Artist, birth, registry  # noqa: E402
from works import CURRENT, RUN, STANDING, STARTS_LEFT, TERMINAL, Work, event, log  # noqa: E402


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
    walls = Path(a.walls).expanduser() if a.walls else None
    if walls and not (walls.is_dir() and any(walls.iterdir())):
        raise SystemExit(f"--walls {walls}: no paintings there")
    temperament = None
    if a.temperament:
        temperament = Path(a.temperament).expanduser().read_text()
        if not temperament.strip():
            raise SystemExit(f"--temperament {a.temperament}: the file is empty")
    note = Path(a.temperament_note).expanduser().read_text() if a.temperament_note else None
    if note is not None and not temperament:
        raise SystemExit("--temperament-note goes with --temperament")
    artist = birth(studio=a.studio, walls=walls, temperament=temperament, temperament_note=note)
    rec = json.loads((artist.home / "birth.json").read_text())
    hung = rec["walls_at_birth"]
    event(f"{artist.name} born ({artist.id}), model and effort in the birth record"
          + (f"; {hung} paintings hung before their first work (the owner's, recreated from recollection)" if hung else "")
          + ("; given a temperament by the owner, the first page of their notebook" if rec.get("temperament_note") else ""))
    print(f"{artist.name} ({artist.id}) is born")


def cmd_paint(a):
    if not CLAUDE.exists():
        raise SystemExit(f"no pinned Claude Code at {CLAUDE} (RUN-15)")
    from config import DEFAULT_BOX, boxes
    box = getattr(a, "box", None) or DEFAULT_BOX  # (the tick gives no box: the default)
    if box not in boxes():
        raise SystemExit(f"no box {box!r}; the boxes: {', '.join(boxes())} (tools/build-engine.sh builds them)")
    w = Work.create(Artist(a.artist), a.theme, a.by, box)
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
    print(f"today: ${budget.spent_today():.2f} of ${budget.daily_cap():.0f}; painting window {budget.window()} "
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


def cmd_sync(a):
    """The site to the NAS now (tools/push.sh does it every 2 minutes); from a terminal, which may reach the NAS."""
    subprocess.run(["/bin/bash", str(REPO / "tools" / "push.sh")])
    print(subprocess.run(["tail", "-1", str(DATA / "run" / "nas.log")], capture_output=True, text=True).stdout.strip())


def cmd_backup(a):
    """The site and the backup to the NAS now."""
    subprocess.run(["/bin/bash", str(REPO / "tools" / "push.sh"), "backup"])
    print(subprocess.run(["tail", "-4", str(DATA / "run" / "nas.log")], capture_output=True, text=True).stdout.strip())


def cmd_tick(a):
    """The owner's standing go (2026-10-07: all three studios, in turn, at night, within the budget, until the time in
    DATA/run/until). Run every 10 minutes by launchd (deploy/mac/): resumes a work a reboot cut off, else starts the
    next studio's work when the window is open and today's budget allows. Never clears an audit stop."""
    from datetime import datetime
    import budget
    if not STANDING.exists() or datetime.now().astimezone() >= datetime.fromisoformat(STANDING.read_text().strip()):
        if budget.OPEN.exists():  # the go the studios were opened for has ended: the night window and the cap again
            budget.OPEN.unlink()
            event(f"the owner's go has ended: painting window {budget.WINDOW} and ${budget.DAILY_USD:.0f} a day again")
        return
    w = open_work()
    if w:
        if runner_alive(w) or w.state["state"] in TERMINAL:
            return
        if w.state["state"] == "stopped":
            if classifier_misfire(w) and auto_withdrawn_today() < 3:
                # Claude's own safety classifier stopped the painter's first reply before any paint was laid: its notice
                # reached the model, so the audit stopped the sitting. Nothing of the work exists yet; it is withdrawn
                # (logged, private) and the next work starts (the owner, 2026-10-10; at most 3 a day)
                cmd_withdraw(argparse.Namespace(why="auto: Claude's safety classifier stopped the painter's first reply, "
                                                    "before any paint was laid"))
                return
            log(f"tick: {w.id} was stopped by the white-room audit; it waits for a person")
            return
        log(f"tick: {w.id} has no runner; resuming it")
        cmd_resume(argparse.Namespace(clear=None))
        return
    starts = int(STARTS_LEFT.read_text().strip()) if STARTS_LEFT.exists() else None
    if starts is not None and starts <= 0:  # the open work, if any, goes on; nothing new starts
        if budget.OPEN.exists():  # the run the studios were opened for is done: the night window and the cap again
            budget.OPEN.unlink()
            event(f"the owner's run is done: painting window {budget.WINDOW} and ${budget.DAILY_USD:.0f} a day again")
        return
    if not budget.in_window() or budget.spent_today() >= budget.daily_cap():
        return
    if budget.window() != "always":  # no new work in a night's last 90 minutes: it would straddle into the next night
        now, end = datetime.now(), int(budget.window().split("-")[1])
        left = (now.replace(hour=end, minute=0, second=0, microsecond=0) - now).total_seconds()
        if 0 < left < 90 * 60:
            return
    reg = registry()
    n, id = sorted((len(Artist(x).works()), x) for x in reg)[0]
    log(f"tick: starting {Artist(id).name}'s work {n + 1} (the owner's standing go until {STANDING.read_text().strip()}"
        + (f", {starts - 1} more after this)" if starts is not None else ")"))
    if starts is not None:
        STARTS_LEFT.write_text(f"{starts - 1}\n")  # used up before the start: a start that fails is not retried forever
    cmd_paint(argparse.Namespace(artist=id, theme=None, by="owner"))


def classifier_misfire(w: Work) -> bool:
    """Stopped only because Claude's safety classifier's notice reached the model, in its first sitting, no chunk run."""
    hits, sittings = w.state.get("hits") or [], w.state.get("sittings") or []
    painted = (w.artist.studio / "paintings" / "lua" / "painting.lua")
    return (len(sittings) == 1 and bool(hits) and all("safety classifier" in h for h in hits)
            and not (painted.exists() and "--@ chunk" in painted.read_text()))


def auto_withdrawn_today() -> int:
    from datetime import date
    h = DATA / "history.md"
    return sum(1 for l in (h.read_text().splitlines() if h.exists() else [])
               if l.startswith(f"- {date.today():%Y-%m-%d}") and "withdrawn by the tick, not finished: auto:" in l)


def cmd_withdraw(a):
    """A work the audit stopped, ended by a person instead of resumed: not finished, contaminated (never public), its
    reason in its manifest and in history.md. Its notebook edits were rolled back when it stopped."""
    from works import now
    w = open_work()
    if not w:
        raise SystemExit("no open work")
    if w.state["state"] != "stopped":
        raise SystemExit(f"{w.id} is {w.state['state']}: only a work the audit stopped is withdrawn")
    subprocess.run([str(w.artist.studio / "bin" / "easel"), "close"], cwd=w.artist.studio, capture_output=True, timeout=120)
    s = w.state
    manifest = {"id": w.id, "artist": s["artist"], "studio": w.artist.name, "number": s["number"], "title": None,
                "mode": s["mode"], "theme": s["theme"], "box": s.get("box"), "started_by": s["started_by"],
                "start": s["created"], "end": now(), "pauses": s.get("pauses", []),
                "sittings": [{k: r.get(k) for k in ("n", "start", "end", "how")} for r in s["sittings"]],
                "audit_hits": s["hits"], "contaminated": True, "replay": None, "replay_verified": False,
                "finished": False, "why": f"withdrawn: {a.why}"}
    (w.pkg / "manifest.json").write_text(json.dumps(manifest, indent=1))
    w.set("not-finished", why=f"withdrawn: {a.why}")
    CURRENT.unlink(missing_ok=True)
    event(f"work {w.id} withdrawn by {'the tick' if a.why.startswith('auto:') else 'a person'}, not finished: {a.why}")
    print(f"{w.id} withdrawn; the next work can start")


def cmd_boxes(a):
    from config import DEFAULT_BOX, PAINTER_BOXES, boxes
    for b in boxes():
        n = sum(1 for l in (PAINTER_BOXES / b / "tubes.md").read_text().splitlines()[2:] if l.startswith("|"))
        print(f"{b}: {n} tubes{' (default)' if b == DEFAULT_BOX else ''}")


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
    b.add_argument("--studio", help="which studio to birth (i, ii, iii); default the first not yet born")
    b.add_argument("--walls", help="a folder of paintings named 1, 2, ... to hang before the first work")
    b.add_argument("--temperament", help="a text file: the owner's temperament for the painter, their notebook's first page")
    b.add_argument("--temperament-note", help="a text file: what visitors read about the temperament (first line: its heading)")
    pp = sub.add_parser("paint")
    pp.add_argument("artist")
    pp.add_argument("--theme")
    pp.add_argument("--box", help="the tube box this work is painted from (default: every; `atelier boxes` lists them)")
    pp.add_argument("--by", required=True, choices=["owner", "operator"])
    r = sub.add_parser("run")
    r.add_argument("work")
    sub.add_parser("status")
    rs = sub.add_parser("resume")
    rs.add_argument("--clear")
    sub.add_parser("next")
    sub.add_parser("tick")
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8800)
    sub.add_parser("export")
    sub.add_parser("boxes")
    wd = sub.add_parser("withdraw")
    wd.add_argument("--why", required=True)
    sub.add_parser("sync")
    sub.add_parser("backup")
    a = p.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    DATA.chmod(0o700)
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
