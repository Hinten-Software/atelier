"""A work, from its brief to the walls (requirements 5.10, RUN-5..9, NFR-9, NFR-10, REC-1, REC-4).

States are kept in DATA/run/<work>/state.json, written atomically on every transition, so a runner that dies
(or a reboot) leaves the work in a state `atelier status` can name and `atelier resume` (a person) can continue.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import audit
from config import (CHECK_PAINTING, CLAUDE, CLAUDE_VERSION, CONTEXT_LIMIT, CRASH_WAITS, DATA, EASEL_MCP, LIMIT_GIVE_UP_S,
                    LIMIT_RETRY_S, MAX_INVOLUNTARY, NODE, REPLAY_EASEL, REPO, TEXTS, TOOLS, artist_env)
from studio import NOTEBOOK, TOOLKIT, Artist, hang, now, prepare, sha256

import importlib.util  # noqa: E402

# claude-paint's viewer (its transcript parser and title rule), loaded by path: it is also called studio.py
_spec = importlib.util.spec_from_file_location("viewer_studio", REPO / "viewer" / "studio.py")
viewer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(viewer)

TERMINAL = {"finished", "not-finished"}
RUN = DATA / "run"
CURRENT = RUN / "current"


def log(msg: str):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    RUN.mkdir(parents=True, exist_ok=True)
    with open(RUN / "runner.log", "a") as f:
        f.write(line + "\n")


def event(msg: str):
    """A dated atelier event (history.md: ENG-5, EXP-10)."""
    with open(DATA / "history.md", "a") as f:
        f.write(f"- {time.strftime('%F %H:%M')} {msg}\n")


def messages() -> dict:
    return json.loads((TEXTS / "messages.json").read_text())


def slug(path: Path) -> str:
    """Claude Code's folder name for a working directory's transcripts."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


class Work:
    def __init__(self, id: str):
        self.id = id
        self.run = RUN / id
        self.pkg = DATA / "works" / id
        self.state = json.loads((self.run / "state.json").read_text())
        self.artist = Artist(self.state["artist"])

    @classmethod
    def create(cls, artist: Artist, theme: str | None, started_by: str) -> "Work":
        if CURRENT.exists():
            raise SystemExit(f"a work is open: {CURRENT.read_text().strip()} (atelier status)")
        number = len(artist.works()) + 1
        id = f"{artist.id}-{number:03d}"
        run, pkg = RUN / id, DATA / "works" / id
        run.mkdir(parents=True)
        pkg.mkdir(parents=True)
        for f in (NOTEBOOK, TOOLKIT):  # as they were before this work (ART-7)
            src = artist.studio / f
            shutil.copy2(src, pkg / f"{Path(f).stem}.before{Path(f).suffix}") if src.exists() else None
        hashes = prepare(artist, theme)
        hashes |= {"system_prompt": sha256(TEXTS / "system_prompt.md"), "settings": sha256(TEXTS / "settings.json"),
                   "messages": sha256(TEXTS / "messages.json"), "brief_template": sha256(TEXTS / "brief.md"),
                   "easel_mcp": sha256(EASEL_MCP), "easel_client": sha256(REPO / "easel-mcp/src/upstream/easel-client.ts"),
                   "replay_easel": sha256(REPLAY_EASEL)}
        shutil.copy2(artist.studio / "BRIEF.md", pkg / "brief.md")
        state = {"id": id, "artist": artist.id, "number": number, "theme": theme, "mode": "themed" if theme else "free",
                 "started_by": started_by, "created": now(), "state": "prepared", "sittings": [], "crashes": 0,
                 "involuntary": 0, "limit_since": None, "hashes": hashes, "hits": []}
        (run / "state.json").write_text(json.dumps(state, indent=1))
        CURRENT.write_text(id)
        w = cls(id)
        hits = w.whiteroom()
        if hits:
            w.state["hits"] = hits
            w.set("stopped")
            raise SystemExit("white-room scan of the prepared studio failed (NFR-9):\n  " + "\n  ".join(hits))
        log(f"{id}: prepared for {artist.name} ({state['mode']}), started by {started_by}")
        event(f"work {id} started for {artist.name} ({state['mode']}{': ' + theme if theme else ''}), by {started_by}")
        return w

    # -- state ------------------------------------------------------------------------------------------------
    def save(self):
        tmp = self.run / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.run / "state.json")

    def set(self, state: str, **extra):
        self.state.update(state=state, **extra)
        self.save()
        log(f"{self.id}: {state}")

    def whiteroom(self) -> list[str]:
        """NFR-9: the prepared studio, the messages and the system prompt."""
        ours = {"BRIEF.md", "notes/easel_guide.md", "notes/research/oil_paint_physics.md", "notes/journal.md",
                "walls/index.md"}
        hits = audit.scan_studio(self.artist.studio, ours)
        for name, text in messages().items():
            hits += audit.scan_text(f"messages.{name}", text, True)
        hits += audit.scan_text("system_prompt", (TEXTS / "system_prompt.md").read_text(), True)
        return hits

    # -- the loop -----------------------------------------------------------------------------------------------
    def go(self):
        """Carry the work through its sittings to the walls (5.10). Returns when it is finished, not finished, or
        stopped for the operator."""
        (self.run / "runner.pid").write_text(str(os.getpid()))
        subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])  # OPS-6
        exporter = Exporter()
        exporter.start()
        try:
            self._loop()
        finally:
            exporter.stop()

    def _loop(self):
        while self.state["state"] not in TERMINAL | {"stopped"}:
            st = self.state["state"]
            if st in ("prepared", "between", "interrupted", "resumed"):
                self.sitting()
            elif st == "limit-wait":
                self.wait_limit()
            elif st == "crash-wait":
                k = min(self.state["crashes"], len(CRASH_WAITS)) - 1
                self.sleep(CRASH_WAITS[k], "crash-wait")
                self.set("between")
            elif st == "finishing":
                self.finish()
            elif st == "sitting":  # found mid-sitting with no process: a reboot or a runner crash
                self.set("interrupted")
                return
            else:
                raise SystemExit(f"{self.id}: unknown state {st!r}")
        (self.run / "runner.pid").unlink(missing_ok=True)

    def sleep(self, seconds: float, why: str):
        log(f"{self.id}: {why}, {int(seconds)} s")
        time.sleep(seconds)

    def wait_limit(self):
        since = self.state["limit_since"] or time.time()
        if time.time() - since > LIMIT_GIVE_UP_S:
            return self.set("not-finished", why="the usage limit held for 7 days")
        until = self.state.get("limit_until") or time.time() + LIMIT_RETRY_S
        self.sleep(max(min(60, LIMIT_RETRY_S), until - time.time()), "usage limit")
        self.set("between")  # a fresh sitting: no limit message ever enters the artist's history (RUN-6)

    # -- one sitting --------------------------------------------------------------------------------------------
    def sitting(self):
        a, n = self.artist, len(self.state["sittings"]) + 1
        msgs = messages()
        message = msgs["first"] if n == 1 else msgs["again"]
        sid = str(uuid.uuid4())
        snap = self.run / f"sitting-{n}-before"  # the artist's own files, to roll back after an audit hit (NFR-10)
        snap.mkdir(exist_ok=True)
        for f in (NOTEBOOK, TOOLKIT):
            if (a.studio / f).exists():
                shutil.copy2(a.studio / f, snap / f)
        cmd = claude_cmd(a.studio, self.run, message, sid, a_model(a), a_effort(a))
        strip_profile(a.config)
        transcript = a.config / "projects" / slug(a.studio) / f"{sid}.jsonl"
        rec = {"n": n, "session": sid, "message": message, "start": now(), "end": None, "how": None,
               "transcript": str(transcript), "date_shown": None, "exit": None}
        self.state["sittings"].append(rec)
        self.set("sitting")
        stream, errf = self.run / f"{sid}.stream.jsonl", self.run / f"{sid}.stderr.txt"
        with open(stream, "w") as out, open(errf, "w") as err:
            proc = subprocess.Popen(cmd, cwd=a.studio, env=artist_env(a.config), stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            watch = Watcher(proc, transcript, set(msgs.values()), a.config)
            watch.start()
            rc = proc.wait()
            watch.stop()
        rec.update(end=now(), exit=rc, date_shown=watch.date_shown)
        result = last_result(stream)
        text = ((result or {}).get("result") or "") + "\n" + errf.read_text(errors="replace")
        if watch.hits:
            rec["how"] = "audit"
            self.state["hits"] += watch.hits
            for f in (NOTEBOOK, TOOLKIT):  # this sitting's edits to the artist's own files are rolled back
                if (snap / f).exists():
                    shutil.copy2(snap / f, a.studio / f)
            self.state["contaminated"] = True
            event(f"work {self.id} sitting {n} stopped by the white-room audit: {watch.hits[0]}")
            return self.set("stopped")
        if watch.context_end:
            rec["how"] = "context"
        elif result and result.get("subtype") == "success" and not result.get("is_error"):
            rec["how"] = "voluntary"
            self.state["reply"] = result.get("result", "")
            return self.set("finishing")
        elif is_limit(text):
            rec["how"] = "limit"
            self.state["limit_since"] = self.state["limit_since"] or time.time()
            self.state["limit_until"] = reset_time(text)
            return self.set("limit-wait")
        else:
            rec["how"] = "crash"
            rec["error"] = text.strip()[-2000:]
            self.state["crashes"] += 1
            if self.state["crashes"] > len(CRASH_WAITS):
                return self.set("not-finished", why="crashed too often")
            return self.set("crash-wait")
        self.state["involuntary"] += 1
        if self.state["involuntary"] > MAX_INVOLUNTARY:
            return self.set("not-finished", why="too many involuntary ends")
        self.set("between")

    # -- finishing ----------------------------------------------------------------------------------------------
    def finish(self):
        """Close the easel, verify the replay, write the work package, hang it (REC-1, REC-4, ART-10)."""
        a, pkg = self.artist, self.pkg
        subprocess.run([str(a.studio / "bin" / "easel"), "close"], cwd=a.studio, env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
                       capture_output=True, timeout=120)
        check = self.run / "check"
        shutil.rmtree(check, ignore_errors=True)
        r = subprocess.run([str(CHECK_PAINTING), str(a.studio), str(check)], capture_output=True, text=True,
                           env=os.environ | {"PATH": f"/opt/homebrew/opt/rustup/bin:{os.environ.get('PATH', '')}"})
        verdict = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("check:")), "check: no verdict")
        verified = verdict.startswith("check: ok")
        (self.run / "check.txt").write_text(r.stdout + r.stderr)
        s = a.studio
        copies = {"paintings/lua/painting.lua": "painting.lua", "notes/journal.md": "journal.md",
                  "out/easel/journal-revisions.jsonl": "journal-revisions.jsonl",
                  "out/easel/write-revisions.jsonl": "write-revisions.jsonl",
                  NOTEBOOK: "notebook.after.md", TOOLKIT: "toolkit.after.lua"}
        for src, dst in copies.items():
            if (s / src).exists():
                shutil.copy2(s / src, pkg / dst)
        if (check / "replayed.png").exists():
            shutil.copy2(check / "replayed.png", pkg / "final.png")
        sessions = pkg / "sessions"
        sessions.mkdir(exist_ok=True)
        for rec in self.state["sittings"]:
            for p in (Path(rec["transcript"]), self.run / f"{rec['session']}.stream.jsonl"):
                if p.exists():
                    shutil.copy2(p, sessions / p.name)
        reply = self.state.get("reply", "")
        title = viewer.title_of(reply)
        (pkg / "reply.md").write_text(reply)
        voluntary = any(r["how"] == "voluntary" for r in self.state["sittings"])
        finished = verified and voluntary and not self.state.get("contaminated")
        manifest = {
            "id": self.id, "artist": a.id, "studio": a.name, "number": self.state["number"], "title": title,
            "mode": self.state["mode"], "theme": self.state["theme"], "started_by": self.state["started_by"],
            "start": self.state["created"], "end": now(),
            "sittings": [{k: r.get(k) for k in ("n", "start", "end", "how", "date_shown", "message")} for r in self.state["sittings"]],
            "model": a_model(a), "model_seen": model_seen(self.state["sittings"]), "effort": a_effort(a),
            "claude_code": CLAUDE_VERSION, "hashes": self.state["hashes"], "audit_hits": self.state["hits"],
            "contaminated": bool(self.state.get("contaminated")), "replay": verdict, "replay_verified": verified,
            "final_sha256": sha256(pkg / "final.png") if (pkg / "final.png").exists() else None, "finished": finished,
        }
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=1))
        hist = a.home / "history"
        for src, dst in ((NOTEBOOK, f"{self.state['number']:03d}-notebook.md"), (TOOLKIT, f"{self.state['number']:03d}-toolkit.lua")):
            if (s / src).exists():
                shutil.copy2(s / src, hist / dst)
        if finished:
            hang(a, len(a.finished()), pkg / "final.png", title, reply)
        CURRENT.unlink(missing_ok=True)
        sync = DATA / "sync.sh"  # OPS-2: the NAS sync, once the NAS side exists
        if sync.exists():
            subprocess.run([str(sync)], capture_output=True)
        event(f"work {self.id} {'finished' if finished else 'ended unfinished'}: {title or 'untitled'} ({verdict})")
        self.set("finished" if finished else "not-finished")


EXPORT_EVERY = 120  # seconds (OPS-4, REC-3)


def export_now():
    """The public export (runner/export.py), with Pillow for the web copies of looks."""
    r = subprocess.run(["/opt/homebrew/bin/uv", "run", "-q", "--with", "pillow", "python3", str(REPO / "runner" / "export.py")],
                       capture_output=True, text=True, env=os.environ | {"ATELIER_DATA": str(DATA)})
    if r.returncode:
        log(f"export failed ({r.returncode}): {(r.stderr or r.stdout).strip()[:500]}")


class Exporter(threading.Thread):
    """Exports while a work is open, and once more when the runner stops."""

    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(EXPORT_EVERY):
            export_now()

    def stop(self):
        self._stop.set()
        export_now()


class Watcher(threading.Thread):
    """Tails a sitting's transcript: the live white-room audit (NFR-10) and the context threshold (RUN-7)."""

    def __init__(self, proc, transcript: Path, messages: set[str], config: Path):
        super().__init__(daemon=True)
        self.proc, self.path, self.messages, self.config = proc, transcript, messages, config
        self.hits: list[str] = []
        self.context_end = False
        self.date_shown = None
        self._stop = threading.Event()
        self._over = False

    def stop(self):
        self._stop.set()
        self.join(timeout=10)
        self.scan()  # whatever arrived last

    def run(self):
        self.offset = 0
        while not self._stop.is_set():
            self.scan()
            self._stop.wait(1.0)

    def scan(self):
        if not self.path.exists():
            return
        with open(self.path, "rb") as fh:
            fh.seek(getattr(self, "offset", 0))
            data = fh.read()
        end = data.rfind(b"\n")
        if end < 0:
            return
        self.offset = getattr(self, "offset", 0) + end + 1
        for line in data[: end + 1].splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "attachment" and (d.get("attachment") or {}).get("type") == "date":
                m = re.search(r"\d{4}-\d{2}-\d{2}", "".join(x.get("content", "") for x in d.get("rendered") or []))
                self.date_shown = m.group(0) if m else None
            hits = audit.check_line(d, self.messages, self.config)
            if hits:
                self.hits += hits
                self.kill()
                return
            usage = (d.get("message") or {}).get("usage") if d.get("type") == "assistant" else None
            if usage:
                ctx = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                self._over = self._over or ctx > CONTEXT_LIMIT
            if self._over and d.get("type") == "user":  # right after a tool result: nothing half done
                self.context_end = True
                self.kill()
                return

    def kill(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def claude_cmd(studio: Path, run: Path, message: str, sid: str, model: str, effort: str) -> list[str]:
    """Claude Code for one sitting, isolated (RUN-13, RUN-14); its MCP config is written to the run folder."""
    mcp = run / "mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"easel": {"command": str(NODE), "args": [str(EASEL_MCP), str(studio)]}}}))
    return [str(CLAUDE), "-p", message, "--session-id", sid, "--model", model, "--effort", effort,
            "--system-prompt", (TEXTS / "system_prompt.md").read_text().strip(),
            "--tools", "", "--allowedTools", ",".join(f"mcp__easel__{t}" for t in TOOLS),
            "--strict-mcp-config", "--mcp-config", str(mcp),
            "--setting-sources", "", "--settings", str(TEXTS / "settings.json"),
            "--disable-slash-commands", "--thinking-display", "summarized",
            "--output-format", "stream-json", "--verbose"]


def a_model(a: Artist) -> str:
    return json.loads((a.home / "birth.json").read_text())["model"]


def a_effort(a: Artist) -> str:
    return json.loads((a.home / "birth.json").read_text())["effort"]


def model_seen(sittings: list[dict]) -> list[str]:
    seen = []
    for rec in sittings:
        p = Path(rec["transcript"])
        if p.exists():
            for line in p.read_text().splitlines():
                m = re.search(r'"model":"(claude-[^"]+)"', line)
                if m and m.group(1) not in seen:
                    seen.append(m.group(1))
    return seen


def strip_profile(config: Path):
    """Claude Code shows the model the account's email as "the user's email" when its stored profile has one
    (spike section 3). Removed before every launch; NFR-10 catches it if Claude Code puts it back mid-sitting."""
    p = config / ".claude.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    acct = d.get("oauthAccount") or {}
    keys = [k for k in ("emailAddress", "displayName", "fullName", "organizationName") if k in acct]
    if keys:
        for k in keys:
            acct.pop(k)
        p.write_text(json.dumps(d, indent=2))


def last_result(stream: Path) -> dict | None:
    res = None
    if stream.exists():
        for line in stream.read_text(errors="replace").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "result":
                res = d
    return res


LIMIT_RE = re.compile(r"(session|weekly|usage|5-hour|opus) limit|limit reached|rate.?limit", re.I)


def is_limit(text: str) -> bool:
    return bool(LIMIT_RE.search(text))


def reset_time(text: str) -> float | None:
    """The epoch of "resets 3pm" / "resets 3:30pm" / "resets Mon 9am" in a limit message (local time), or None."""
    m = re.search(r"resets?\s+(?:at\s+)?(?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)", text, re.I)
    if not m:
        return None
    day, h, mi, ap = m.group(1), int(m.group(2)) % 12, int(m.group(3) or 0), m.group(4).lower()
    h += 12 if ap == "pm" else 0
    t = datetime.now().replace(hour=h, minute=mi, second=0, microsecond=0)
    if day:
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        t += timedelta(days=(days.index(day.lower()[:3]) - t.weekday()) % 7)
    while t <= datetime.now():
        t += timedelta(days=7 if day else 1)
    return t.timestamp() + 60  # a minute's grace
