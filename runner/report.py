#!/usr/bin/env python3
"""The morning report (the owner, 2026-10-11): what the night did and what, if anything, needs a person.

    python3 runner/report.py [--hours 24] [--quiet]

Run at 07:30 by launchd (deploy/mac/atelier.report.plist). Reads only what the runner already writes (history.md,
the works' manifests, the ledger, the logs); changes nothing. Writes DATA/run/reports/<date>.md and shows a macOS
notification: "nothing to do", or how many things need a person (--quiet: no notification).
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA  # noqa: E402
from works import CURRENT, EXPORT_FAILED, STANDING  # noqa: E402

RUN = DATA / "run"
STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?) (.*)$")


def stamped(path: Path, since: datetime, prefix: str = "") -> list[tuple[datetime, str]]:
    out = []
    for line in path.read_text(errors="replace").splitlines() if path.exists() else []:
        m = STAMP.match(line.removeprefix(prefix))
        if m:
            t = datetime.fromisoformat(m.group(1))
            if t >= since:
                out.append((t, m.group(2)))
    return out


def report(hours: float) -> tuple[str, list[str]]:
    now = datetime.now()
    since = now - timedelta(hours=hours)
    needs: list[str] = []
    lines = [f"# The atelier, {now:%A %-d %B %Y, %H:%M}", "", f"Since {since:%a %H:%M}."]

    # the works that ended
    done = []
    for m in sorted((DATA / "works").glob("*/manifest.json")):
        d = json.loads(m.read_text())
        end = d.get("end")
        if not end or end == "unknown":
            continue
        e = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        if e >= since:
            done.append(d)
    ledger = json.loads((RUN / "ledger.json").read_text()) if (RUN / "ledger.json").exists() else {}
    finished = [d for d in done if d.get("finished")]
    lines += ["", f"## Works ({len(finished)} finished, {len(done) - len(finished)} not)"]
    for d in done:
        usd = (ledger.get("works") or {}).get(d["id"])
        cost = f", ${usd:.2f}" if usd is not None else ""
        if d.get("finished"):
            ok = "replay ok" if d.get("replay_verified") else "REPLAY NOT VERIFIED"
            lines.append(f"- {d['id']} {d.get('title') or 'UNTITLED'} ({ok}{cost})")
            if not d.get("title"):
                needs.append(f"{d['id']} was hung without a title: the painter's words are in works/{d['id']}/reply.md")
            if not d.get("replay_verified"):  # a record now, not a gate: the painter's canvas hangs either way
                needs.append(f"{d['id']}: hung, but its replay check did not pass (works/{d['id']}/check.txt)")
        else:
            lines.append(f"- {d['id']} not finished: {(d.get('why') or '')[:160]}{cost}")
    if not done:
        lines.append("- none")

    # the atelier's events: stops, set-asides, the go
    events = stamped(DATA / "history.md", since, "- ")
    notable = [(t, x) for t, x in events if re.search(r"^work \S+ (sitting \d+ stopped by|withdrawn|started afresh)|go has ended|"
                                                      r"run is done|ceiling", x)]
    if notable:
        lines += ["", "## Events"] + [f"- {t:%a %H:%M} {x[:300]}" for t, x in notable]
    for t, x in notable:
        # only the tick's own set-aside line (an event that merely mentions one, e.g. a rule fixed, is not)
        if m := re.match(r"work (\S+) withdrawn by the tick, not finished: auto: set aside", x):
            needs.append(f"{m.group(1)} was set aside after an audit stop: is the stop a rule to fix?")

    # what is open now
    lines += ["", "## Now"]
    cur = CURRENT.read_text().strip() if CURRENT.exists() else None
    if cur:
        st = json.loads((RUN / cur / "state.json").read_text())
        lines.append(f"- open: {cur}, {st.get('state')}")
        if st.get("state") == "stopped":
            needs.append(f"{cur} is stopped by the audit and waits for a person: {(st.get('hits') or ['?'])[0][:200]}")
    else:
        lines.append("- no work open")
    if STANDING.exists():
        until = datetime.fromisoformat(STANDING.read_text().strip()).astimezone().replace(tzinfo=None)
        left = (until - now).days
        lines.append(f"- the standing go runs until {until:%-d %B %H:%M}" if until > now else
                     f"- the standing go ENDED {until:%-d %B %H:%M}: nothing paints tonight")
        if until <= now:
            needs.append("the standing go has ended: nothing paints tonight unless it is renewed")
        elif left < 3:
            needs.append(f"the standing go ends in {left} day(s), {until:%-d %B}")
    days = ledger.get("days") or {}
    spent = [f"{d} ${v:.2f}" for d, v in sorted(days.items())[-3:]]
    lines.append(f"- spent: {', '.join(spent) or 'nothing yet'}")

    # the site and the NAS
    lines += ["", "## Site and NAS"]
    if EXPORT_FAILED.exists():
        lines.append(f"- the site export FAILS: {EXPORT_FAILED.read_text().strip()[:300]}")
        needs.append("the site export fails (the tick keeps trying): " + EXPORT_FAILED.read_text().strip()[:200])
    nas = stamped(RUN / "nas.log", since)
    bad = [(t, x) for t, x in nas if "failed" in x]
    sync_ok = [t for t, x in nas if x.startswith("site sync: ok")]
    backup_ok = [t for t, x in nas if x.startswith("backup data: ok")]
    lines.append(f"- site sync: last ok {sync_ok[-1]:%a %H:%M}" if sync_ok else "- site sync: NONE OK in this period")
    lines.append(f"- backup: last ok {backup_ok[-1]:%a %H:%M}" if backup_ok else "- backup: NONE OK in this period")
    if bad:
        lines.append(f"- {len(bad)} failures, the last: {bad[-1][0]:%a %H:%M} {bad[-1][1][:200]}")
    if not sync_ok or (now - sync_ok[-1]) > timedelta(minutes=30):
        needs.append("the site has not reached the NAS for over 30 minutes (run/nas.log)")
    if not backup_ok:
        needs.append("no backup reached the NAS in this period (run/nas.log)")
    crashes = [x for t, x in stamped(RUN / "runner.log", since) if "Traceback" in x or "crash" in x.lower()]
    if crashes:
        needs.append(f"the runner logged {len(crashes)} crash line(s) (run/runner.log)")

    lines += ["", "## Needs a person"] + ([f"- {n}" for n in needs] or ["- nothing"])
    return "\n".join(lines) + "\n", needs


def notify(title: str, text: str):
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{esc(text)}" with title "{esc(title)}"'],
                   capture_output=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    text, needs = report(a.hours)
    out = RUN / "reports"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{datetime.now():%Y-%m-%d}.md"
    f.write_text(text)
    print(text)
    if not a.quiet:
        fin = len(re.findall(r"^- \S+ .*\((?:replay|REPLAY)", text, re.M))
        notify("Atelier: nothing to do" if not needs else f"Atelier: {len(needs)} thing(s) need you",
               f"{fin} painting(s) finished. " + ("; ".join(needs)[:180] if needs else "All well."))


if __name__ == "__main__":
    main()
