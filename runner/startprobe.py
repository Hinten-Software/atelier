#!/usr/bin/env python3
"""How often Claude's safety classifier stops a painter's start (2026-10-12).

    python3 runner/startprobe.py [-n 20] [i ii iii]

Every classifier stop so far (ii-004, ii-006, iii-004, iii-007) came at the same point: the painter's reply right
after it read the brief. This runs only that far, many times: the production setup (runner/probes.py's throwaway
root under /Users/Shared, the artist's model and effort, the real first message) in a copy of each studio's
starting state (notebook, toolkit, wall cards, so the brief and walls/list are the studio's own), then stops the
run as soon as the second reply is done or the classifier stopped it. The real studios are not touched.

Each run is about one cent. The results go to DATA/run/startprobe/<time>/: results.json, and the transcript of every
stopped run (the model's withheld reply is never in it; what led up to it is).
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CLAUDE, DATA, artist_env  # noqa: E402
from probes import Probe  # noqa: E402
from studio import NOTEBOOK, TOOLKIT, Artist, prepare  # noqa: E402
from works import a_effort, a_model, claude_cmd, messages, slug, strip_profile  # noqa: E402

STOP_NOTICE = "stopped by a safety classifier"
WAIT = 300  # s: a start that isn't done in five minutes is recorded as such


class StartProbe(Probe):
    """A throwaway copy of a studio as a new work finds it."""
    def __init__(self, artist: Artist):
        super().__init__(None)
        self.home = self.root / ".home"
        for f in (NOTEBOOK, TOOLKIT):
            if (artist.studio / f).exists():
                shutil.copy2(artist.studio / f, self.studio / f)
        if (artist.home / "walls").is_dir():
            shutil.copytree(artist.home / "walls", self.home / "walls")


def start(artist: Artist, n: int, out: Path) -> dict:
    p = StartProbe(artist)
    run_dir = p.root / ".run"
    run_dir.mkdir()
    rec = {"studio": artist.id, "n": n, "outcome": None, "calls": [], "usd": None}
    proc = None
    try:
        prepare(p, None)
        strip_profile(p.config)
        sid = str(uuid.uuid4())
        cmd = claude_cmd(p.studio, run_dir, messages()["first"], sid, a_model(artist), a_effort(artist), run_dir / "replies.jsonl")
        proc = subprocess.Popen(cmd, cwd=p.studio, env=artist_env(p.config, p.root), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        timer = threading.Timer(WAIT, lambda: os.killpg(proc.pid, signal.SIGTERM))
        timer.start()
        results = 0
        for line in proc.stdout:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if STOP_NOTICE in line:
                rec["outcome"] = f"stopped at reply {results + 1}"
                break
            if d.get("type") == "result":
                rec["outcome"], rec["usd"] = "clean (ended)", d.get("total_cost_usd")
                break
            content = (d.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if b.get("type") == "tool_use":
                    rec["calls"].append(f"{b['name'].removeprefix('mcp__easel__')} {json.dumps(b.get('input'))[:60]}")
                elif b.get("type") == "tool_result":
                    results += 1
            if results >= 2:  # the reply after the first tool result is done, and its call came back
                rec["outcome"] = "clean"
                break
        timer.cancel()
        if rec["outcome"] is None:
            rec["outcome"] = "no outcome (timed out or ended early)"
        transcript = p.config / "projects" / slug(p.studio) / f"{sid}.jsonl"
        if rec["outcome"].startswith("stopped") and transcript.exists():
            shutil.copy2(transcript, out / f"{artist.id}-{n:02d}-{sid}.jsonl")
        return rec
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=30)
        subprocess.run([str(p.studio / "bin" / "easel"), "close"], cwd=p.studio, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
        shutil.rmtree(p.root, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-n", type=int, default=20, help="starts per studio")
    ap.add_argument("studios", nargs="*", default=["i", "ii", "iii"])
    args = ap.parse_args()
    if not CLAUDE.exists():
        raise SystemExit(f"no pinned Claude Code at {CLAUDE}")
    out = DATA / "run" / "startprobe" / time.strftime("%Y%m%d-%H%M")
    out.mkdir(parents=True, exist_ok=True)
    artists = {s: Artist(s) for s in args.studios}
    jobs = [(artists[s], i) for i in range(1, args.n + 1) for s in args.studios]
    results = []
    with ThreadPoolExecutor(max_workers=len(args.studios)) as pool:  # one start per studio at a time
        for rec in pool.map(lambda j: start(*j, out), jobs):
            results.append(rec)
            print(f"{rec['studio']:>3} {rec['n']:2d}  {rec['outcome']}  {' / '.join(rec['calls'][:2])}", flush=True)
            (out / "results.json").write_text(json.dumps(results, indent=1))
    print()
    for s in args.studios:
        mine = [r for r in results if r["studio"] == s]
        stopped = sum(r["outcome"].startswith("stopped") for r in mine)
        other = sum(not r["outcome"].startswith(("stopped", "clean")) for r in mine)
        print(f"Studio {s.upper()}: {stopped} of {len(mine)} stopped" + (f", {other} without an outcome" if other else ""))
    print(f"results: {out}")


if __name__ == "__main__":
    main()
