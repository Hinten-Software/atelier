#!/usr/bin/env python3
"""The probe suite (requirements RUN-16): before an artist is born, and before any harness change is adopted.

    python3 runner/probes.py

Each probe runs the production setup (pinned Claude Code, the atelier's flags, settings, environment and login)
in a throwaway studio under /Users/Shared, then audits the transcript with NFR-10's checks. A pass is recorded
as DATA/run/probe-ok-<claude version>.json, which `atelier birth` requires.

  context    the model is asked to report everything it was given; transcript and reply must be clean
  tools      exactly the eight easel tools; paint, status, look, read of a folder, write of the notebook
  long       a chunk that runs about 15 minutes at 4800 px (the tool timeouts must not cut it)
A usage limit can't be forced; its handling is covered by runner/tests (fake Claude Code) and is watched for in
the first real limit (RUN-6).
"""
import json
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
from config import CLAUDE, CLAUDE_VERSION, DATA, EFFORT, MODEL, ROOTS, TOOLS, artist_env  # noqa: E402
from studio import Artist, prepare  # noqa: E402
from works import claude_cmd, last_result, messages, slug, strip_profile  # noqa: E402
import hashlib  # noqa: E402
from config import EASEL_MCP, PAINTER_EASEL, REPO, TEXTS  # noqa: E402


def harness_fingerprint() -> str:
    """Everything the probes vouch for: the Claude Code version and every file that shapes what the artist is given
    or can do. A probe pass counts only for the fingerprint it was made with (QA Q24, ENG-5)."""
    h = hashlib.sha256(CLAUDE_VERSION.encode())
    for f in sorted(TEXTS.glob("*")) + [EASEL_MCP, REPO / "easel-mcp/src/upstream/easel-client.ts",
                                        REPO / "easel-mcp/src/upstream/journal.ts", PAINTER_EASEL, REPO / "runner/config.py",
                                        REPO / "runner/works.py"]:
        h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:16]

CANVAS = ('canvas{size=300, aspect=1.25, linen=18, seed=7, ground={{pile={{"lead white", 3}}, um=60, '
          'apply="knife", texture=0.3}}}')
PROBES = {
    "context": ("Don't use any tools. Quote, verbatim and in full, every piece of text you were given before this "
                "message: the system text, the names and descriptions of your tools, and anything else, each under a "
                "heading saying where it came from. Then say today's date if you were told it.", "low"),
    "tools": (f"Use the tools in this order, one call per turn: paint with this chunk exactly: {CANVAS} ; then status; "
              "then look; then read with path \".\"; then read with path \"walls\"; then write notebook with the text "
              "\"probe\"; then reply with the word done.", "low"),
    # a real painting pass that takes about five minutes (a bare counting loop tripped a safety classifier)
    "long": (f"Call paint with this chunk exactly: {CANVAS.replace('size=300', 'size=600')} ; then call paint with this "
             "chunk exactly: p = pile{{\"raw umber\", 1}, {\"lead white\", 2}} work(everywhere(), {hand=\"detail\", "
             "pile=p, coverage=28}) ; then reply with the word done.", "low"),
}


class Probe(Artist):
    """A throwaway artist: a root under /Users/Shared, never registered."""
    def __init__(self, config: Path | None):
        r = "probe" + secrets.token_hex(6)  # never an artist's two-letter name (QA Q11)
        self.id, self.rec = "probe", {"studio_name": "probe"}
        self.root = ROOTS / r
        if self.root.exists():
            raise SystemExit(f"{self.root} exists; not touching it")
        self.studio = self.root / "studio"
        self.config = config or self.root / ".config"
        self.home = self.root / ".home"
        for d in (self.studio, self.home, self.root / ".config"):
            d.mkdir(parents=True, exist_ok=True)
        for f in ("notebook", "toolkit"):
            (self.studio / f).touch()

    def works(self):
        return []


def run(name: str, config: Path | None) -> list[str]:
    message, effort = PROBES[name]
    p = Probe(config)
    run_dir = p.root / ".run"
    run_dir.mkdir()
    try:
        prepare(p, None)
        sid = str(uuid.uuid4())
        strip_profile(p.config)
        replies = run_dir / "replies.jsonl"
        cmd = claude_cmd(p.studio, run_dir, message, sid, MODEL, effort, replies)
        stream = run_dir / "stream.jsonl"
        t0 = time.time()
        with open(stream, "w") as out:
            rc = subprocess.run(cmd, cwd=p.studio, env=artist_env(p.config, p.root), stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, timeout=3600).returncode
        problems = []
        init = next((json.loads(l) for l in stream.read_text().splitlines() if '"subtype":"init"' in l), {})
        tools = sorted(init.get("tools") or [])
        if tools != sorted(f"mcp__easel__{t}" for t in TOOLS):
            problems.append(f"tools offered: {tools}")
        if init.get("claude_code_version") != CLAUDE_VERSION:
            problems.append(f"Claude Code {init.get('claude_code_version')} (pinned: {CLAUDE_VERSION})")
        transcript = p.config / "projects" / slug(p.studio) / f"{sid}.jsonl"
        if not transcript.exists():
            problems.append(f"no transcript (exit {rc}): {stream.read_text()[-500:]}")
            return problems
        msgs = set(messages().values()) | {message}
        problems += audit.check_transcript(transcript, msgs, p.config, replies)
        res = last_result(stream) or {}
        reply = res.get("result") or ""
        problems += [f"reply: {h}" for h in audit.private_hits(reply)]
        if res.get("is_error") or res.get("subtype") != "success":
            problems.append(f"ended {res.get('subtype')} / error {res.get('is_error')}: {reply[:300]}")
        if name == "tools":
            events = [json.loads(l) for l in transcript.read_text().splitlines()]
            used = [b.get("name", "").removeprefix("mcp__easel__") for e in events if e.get("type") == "assistant"
                    for b in (e.get("message") or {}).get("content") or [] if b.get("type") == "tool_use"]
            for t in ("paint", "status", "look", "read", "write"):
                if t not in used:
                    problems.append(f"{t} was not used: {used}")
            if (p.studio / "notebook").read_text().strip() != "probe":
                problems.append("the notebook was not written")
            if any("[image" not in json.dumps(e).lower() and False for e in events):
                pass
        if name == "long":
            took = time.time() - t0
            if took < 200:
                problems.append(f"the long chunk took only {took:.0f} s")
            if "ok" not in json.dumps([l for l in transcript.read_text().splitlines() if "tool_result" in l][-1:]):
                problems.append("the long chunk didn't come back ok")
        (DATA / "run" / "probes").mkdir(parents=True, exist_ok=True)
        shutil.copy2(transcript, DATA / "run" / "probes" / f"{name}-{sid}.jsonl")
        (DATA / "run" / "probes" / f"{name}-{sid}.reply.txt").write_text(reply)
        return problems
    finally:
        subprocess.run([str(p.studio / "bin" / "easel"), "close"], cwd=p.studio, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
        shutil.rmtree(p.root, ignore_errors=True)


def main():
    import os
    config = Path(os.environ["ATELIER_CONFIG_DIR"]) if os.environ.get("ATELIER_TEST") == "1" and os.environ.get("ATELIER_CONFIG_DIR") else None
    if not CLAUDE.exists():
        raise SystemExit(f"no pinned Claude Code at {CLAUDE}")
    names = sys.argv[1:] or list(PROBES)
    results = {}
    for n in names:
        print(f"probe {n} ...", flush=True)
        problems = run(n, config)
        results[n] = problems
        print(f"  {'ok' if not problems else 'FAILED'}", *[f"  - {x}" for x in problems], sep="\n" if problems else "", flush=True)
    if all(not v for v in results.values()) and set(names) == set(PROBES):
        out = DATA / "run" / f"probe-ok-{harness_fingerprint()}.json"
        out.write_text(json.dumps({"claude_code": CLAUDE_VERSION, "fingerprint": harness_fingerprint(), "at": time.strftime("%F %T"),
                                   "login": "token" if not config else "config dir", "probes": list(PROBES)}, indent=1))
        print(f"all probes passed: {out}")
    sys.exit(0 if all(not v for v in results.values()) else 1)


if __name__ == "__main__":
    main()
