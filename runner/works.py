"""A work, from its brief to the walls (requirements 5.10, RUN-5..9, NFR-9, NFR-10, REC-1, REC-4).

States are kept in DATA/run/<work>/state.json, written atomically on every transition, so a runner that dies
(or a reboot) leaves the work in a state `atelier status` can name and `atelier resume` (a person) can continue.
"""
import base64
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import audit
from config import (CHECK_PAINTING, CLAUDE, CLAUDE_VERSION, CONTEXT_LIMIT, CRASH_WAITS, DATA, EASEL_MCP, LIMIT_GIVE_UP_S,
                    LIMIT_RETRY_S, MAX_INVOLUNTARY, NODE, PAINTER_EASEL, REPLAY_EASEL, REPO, TEXTS, TOOLS, artist_env)
from studio import NOTEBOOK, TOOLKIT, Artist, hang, now, prepare, sha256

# claude-paint's viewer (its transcript parser and title rule), loaded by path: it is also called studio.py
_spec = importlib.util.spec_from_file_location("viewer_studio", REPO / "viewer" / "studio.py")
viewer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(viewer)

TERMINAL = {"finished", "not-finished"}
RUN = DATA / "run"
CURRENT = RUN / "current"
JOURNAL = "notes/journal.md"
TRANSCRIPT_GRACE = 90  # seconds: a sitting whose transcript hasn't appeared by then can't be audited (QA Q6)
KILL_GRACE = 30        # seconds between SIGTERM and SIGKILL (QA Q21)


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


def boot_time() -> str:
    """When the machine last started: a pid recorded before a reboot names some other process after it."""
    return subprocess.run(["/usr/sbin/sysctl", "-n", "kern.boottime"], capture_output=True, text=True).stdout.strip()


def repo_commit() -> str:
    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    return r.stdout.strip() + ("+uncommitted" if dirty else "")


def archive_engines() -> dict:
    """Both easels, kept by hash, so any work replays with the binaries that painted it (ENG-3)."""
    out = {}
    for name, path in (("painter", PAINTER_EASEL), ("replay", REPLAY_EASEL)):
        h = sha256(path)
        dest = DATA / "archive" / "engines" / h / name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        out[f"{name}_easel"] = h
    return out


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
        befores = {}
        for f in (NOTEBOOK, TOOLKIT):  # as they were before this work (ART-7)
            src = artist.studio / f
            befores[f] = src.read_bytes() if src.exists() else b""
        hashes = prepare(artist, theme)
        mcp = {"mcpServers": {"easel": {"command": str(NODE), "args": [str(EASEL_MCP), "<studio>", "<reply log>"]}}}
        hashes |= {"system_prompt": sha256(TEXTS / "system_prompt.md"), "settings": sha256(TEXTS / "settings.json"),
                   "messages": sha256(TEXTS / "messages.json"), "brief_template": sha256(TEXTS / "brief.md"),
                   "easel_mcp": sha256(EASEL_MCP), "easel_client": sha256(REPO / "easel-mcp/src/upstream/easel-client.ts"),
                   "mcp_config": __import__("hashlib").sha256(json.dumps(mcp, sort_keys=True).encode()).hexdigest(),
                   "repo_commit": repo_commit(), "engine_upstream": "claude-paint a198dd055964b77882b42925ff949043d5e334e5"}
        hashes |= archive_engines()
        # NFR-9 before anything is recorded as a work: a failed scan leaves nothing behind but the reason (QA Q5)
        hits = whiteroom(artist)
        if hits:
            shutil.rmtree(run)
            shutil.rmtree(pkg)
            raise SystemExit("white-room scan of the prepared studio failed (NFR-9); fix the cause and start again:\n  "
                             + "\n  ".join(hits))
        for f, data in befores.items():
            (pkg / f"{Path(f).stem}.before{Path(f).suffix}").write_bytes(data)
        shutil.copy2(artist.studio / "BRIEF.md", pkg / "brief.md")
        state = {"id": id, "artist": artist.id, "number": number, "theme": theme, "mode": "themed" if theme else "free",
                 "started_by": started_by, "created": now(), "state": "prepared", "sittings": [], "crashes": 0,
                 "involuntary": 0, "limit_since": None, "pauses": [], "hashes": hashes, "hits": []}
        (run / "state.json").write_text(json.dumps(state, indent=1))
        CURRENT.write_text(id)
        log(f"{id}: prepared for {artist.name} ({state['mode']}), started by {started_by}")
        event(f"work {id} started for {artist.name} ({state['mode']}{': ' + theme if theme else ''}), by {started_by}")
        return cls(id)

    # -- state ------------------------------------------------------------------------------------------------
    def save(self):
        tmp = self.run / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.run / "state.json")

    def set(self, state: str, **extra):
        self.state.update(state=state, **extra)
        self.save()
        log(f"{self.id}: {state}")

    # -- the loop -----------------------------------------------------------------------------------------------
    def go(self):
        """Carry the work through its sittings to the walls (5.10). Returns when it is finished, not finished, or
        stopped for the operator."""
        (self.run / "runner.pid").write_text(json.dumps({"pid": os.getpid(), "boot": boot_time()}))
        subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])  # OPS-6
        exporter = Exporter()
        exporter.start()
        try:
            self._loop()
        finally:
            exporter.stop()
            (self.run / "runner.pid").unlink(missing_ok=True)

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

    def sleep(self, seconds: float, why: str):
        log(f"{self.id}: {why}, {int(seconds)} s")
        time.sleep(seconds)

    def wait_limit(self):
        since = self.state["limit_since"] or time.time()
        if time.time() - since > LIMIT_GIVE_UP_S:
            return self.set("not-finished", why="the usage limit held for 7 days")
        until = self.state.get("limit_until") or time.time() + LIMIT_RETRY_S
        start = now()
        self.sleep(max(min(60, LIMIT_RETRY_S), until - time.time()), "usage limit")
        self.state["pauses"].append({"from": start, "to": now(), "why": "usage limit"})
        self.set("between")  # a fresh sitting: no limit message ever enters the artist's history (RUN-6)

    # -- one sitting --------------------------------------------------------------------------------------------
    def kill_leftover(self):
        """A Claude Code that outlived its runner (kill -9 of the runner, QA Q9): stop it before another sitting."""
        last = self.state["sittings"][-1] if self.state["sittings"] else None
        if not last or not last.get("pgid"):
            return
        ps = subprocess.run(["/bin/ps", "-o", "pid=,command=", "-g", str(last["pgid"])], capture_output=True, text=True).stdout
        if last["session"] in ps:  # the process group is still that sitting's Claude Code
            log(f"{self.id}: stopping the previous sitting's Claude Code (pgid {last['pgid']})")
            stop_group(last["pgid"])

    def sitting(self):
        a, n = self.artist, len(self.state["sittings"]) + 1
        self.kill_leftover()
        msgs = messages()
        painted = (a.studio / "paintings" / "lua" / "painting.lua").exists()
        message = msgs["again"] if painted else msgs["first"]  # "as you left it" only if there is a painting (QA Q19)
        sid = str(uuid.uuid4())
        snap = self.run / f"sitting-{n}-before"  # the artist's own files, to roll back after an audit hit (NFR-10)
        snap.mkdir(exist_ok=True)
        for f in (NOTEBOOK, TOOLKIT, JOURNAL):
            if (a.studio / f).exists():
                (snap / Path(f).name).write_bytes((a.studio / f).read_bytes())
        replies = self.run / f"{sid}.replies.jsonl"
        cmd = claude_cmd(a.studio, self.run, message, sid, a_model(a), a_effort(a), replies)
        strip_profile(a.config)
        transcript = a.config / "projects" / slug(a.studio) / f"{sid}.jsonl"
        rec = {"n": n, "session": sid, "message": message, "start": now(), "end": None, "how": None,
               "transcript": str(transcript), "date_shown": None, "exit": None, "pgid": None}
        self.state["sittings"].append(rec)
        self.set("sitting")
        stream, errf = self.run / f"{sid}.stream.jsonl", self.run / f"{sid}.stderr.txt"
        with open(stream, "w") as out, open(errf, "w") as err:
            proc = subprocess.Popen(cmd, cwd=a.studio, env=artist_env(a.config, a.root), stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            rec["pgid"] = proc.pid
            self.save()
            watch = Watcher(proc, transcript, set(msgs.values()), a.config, replies)
            watch.start()
            rc = proc.wait()
            watch.stop()
        rec.update(end=now(), exit=rc, date_shown=watch.date_shown)
        result = last_result(stream)
        text = ((result or {}).get("result") or "") + "\n" + errf.read_text(errors="replace")
        if watch.hits:
            rec["how"] = "audit"
            self.state["hits"] += watch.hits
            for f in (NOTEBOOK, TOOLKIT, JOURNAL):  # this sitting's writes to the artist's files are rolled back
                if (snap / Path(f).name).exists():
                    (a.studio / f).write_bytes((snap / Path(f).name).read_bytes())
            self.state["contaminated"] = True
            event(f"work {self.id} sitting {n} stopped by the white-room audit: {watch.hits[0]}")
            return self.set("stopped")
        if result and result.get("subtype") == "success" and not result.get("is_error") and not watch.context_end:
            rec["how"] = "voluntary"
            self.state["reply"] = result.get("result", "")
            self.state["limit_since"] = None
            return self.set("finishing")
        if watch.context_end:
            rec["how"] = "context"
        elif is_limit(text):
            rec["how"] = "limit"
            self.state["limit_since"] = self.state["limit_since"] or time.time()
            self.state["limit_until"] = reset_time(text)
            return self.set("limit-wait")
        else:
            rec["how"] = "crash"
            rec["error"] = text.strip()[-2000:]
            self.state["crashes"] += 1
            self.state["limit_since"] = None
            if self.state["crashes"] > len(CRASH_WAITS):
                return self.set("not-finished", why="crashed too often")
            return self.set("crash-wait")
        self.state["limit_since"] = None  # a limit counts from the last unbroken run of limits (QA Q10)
        self.state["involuntary"] += 1
        if self.state["involuntary"] > MAX_INVOLUNTARY:
            return self.set("not-finished", why="too many involuntary ends")
        self.set("between")

    # -- finishing ----------------------------------------------------------------------------------------------
    def finish(self):
        """Close the easel, verify the replay, write the work package, hang it (REC-1, REC-4, ART-10). Safe to run
        again after a failure midway (QA Q8): every step either repeats harmlessly or is skipped once done."""
        a, pkg, s = self.artist, self.pkg, self.artist.studio
        done = self.state.setdefault("finish_done", [])
        if "check" not in done:
            subprocess.run([str(s / "bin" / "easel"), "close"], cwd=s, capture_output=True, timeout=120,
                           env={"PATH": "/usr/bin:/bin", "HOME": str(a.root)})
            check = self.run / "check"
            shutil.rmtree(check, ignore_errors=True)
            r = subprocess.run([str(CHECK_PAINTING), str(s), str(check)], capture_output=True, text=True,
                               env=os.environ | {"EASEL_NO_BUILD": "1", "PATH": f"/opt/homebrew/opt/rustup/bin:{os.environ.get('PATH', '')}"})
            verdict = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("check:")), "check: no verdict")
            (self.run / "check.txt").write_text(r.stdout + r.stderr)
            self.state.update(verdict=verdict, verified=verdict.startswith("check: ok"))
            if (check / "replayed.png").exists():
                shutil.copy2(check / "replayed.png", pkg / "final.png")
            done.append("check")
            self.save()
        if "package" not in done:
            copies = {"paintings/lua/painting.lua": "painting.lua", JOURNAL: "journal.md",
                      "out/easel/journal-revisions.jsonl": "journal-revisions.jsonl",
                      "out/easel/write-revisions.jsonl": "write-revisions.jsonl",
                      NOTEBOOK: "notebook.after.md", TOOLKIT: "toolkit.after.lua"}
            for src, dst in copies.items():
                if (s / src).exists():
                    shutil.copy2(s / src, pkg / dst)
            sessions = pkg / "sessions"
            sessions.mkdir(exist_ok=True)
            for rec in self.state["sittings"]:
                for p in (Path(rec["transcript"]), self.run / f"{rec['session']}.stream.jsonl",
                          self.run / f"{rec['session']}.replies.jsonl"):
                    if p.exists():
                        shutil.copy2(p, sessions / p.name)
            write_timeline(pkg, [Path(r["transcript"]) for r in self.state["sittings"]])
            (pkg / "reply.md").write_text(self.state.get("reply", ""))
            hist = a.home / "history"
            hist.mkdir(parents=True, exist_ok=True)
            for src, dst in ((NOTEBOOK, f"{self.state['number']:03d}-notebook.md"), (TOOLKIT, f"{self.state['number']:03d}-toolkit.lua")):
                if (s / src).exists():
                    shutil.copy2(s / src, hist / dst)
            done.append("package")
            self.save()
        reply = self.state.get("reply", "")
        title = viewer.title_of(reply)
        voluntary = any(r["how"] == "voluntary" for r in self.state["sittings"])
        finished = self.state.get("verified", False) and voluntary and not self.state.get("contaminated")
        if finished and "hung" not in done:
            hang(a, len(a.finished()) + 1, pkg / "final.png", title, reply)
            done.append("hung")
            self.save()
        manifest = {
            "id": self.id, "artist": a.id, "studio": a.name, "number": self.state["number"], "title": title,
            "mode": self.state["mode"], "theme": self.state["theme"], "started_by": self.state["started_by"],
            "start": self.state["created"], "end": now(), "pauses": self.state.get("pauses", []),
            "sittings": [{k: r.get(k) for k in ("n", "start", "end", "how", "date_shown", "message")} for r in self.state["sittings"]],
            "model": a_model(a), "model_seen": model_seen(self.state["sittings"]), "effort": a_effort(a),
            "claude_code": CLAUDE_VERSION, "hashes": self.state["hashes"], "audit_hits": self.state["hits"],
            "contaminated": bool(self.state.get("contaminated")), "replay": self.state.get("verdict"),
            "replay_verified": self.state.get("verified", False),
            "final_sha256": sha256(pkg / "final.png") if (pkg / "final.png").exists() else None,
            "finished": finished,  # written last: only once it hangs (QA Q8)
        }
        tmp = pkg / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=1))
        tmp.replace(pkg / "manifest.json")
        CURRENT.unlink(missing_ok=True)
        sync = DATA / "sync.sh"  # OPS-2: the NAS sync, once the NAS side exists
        if sync.exists():
            subprocess.run([str(sync)], capture_output=True)
        event(f"work {self.id} {'finished' if finished else 'ended unfinished'}: {title or 'untitled'} ({self.state.get('verdict')})")
        self.set("finished" if finished else "not-finished")


def write_timeline(pkg: Path, transcripts: list[Path]):
    """timeline.json and looks/: the work replays in the viewer from its package alone (REC-1, M1 check 8)."""
    files = [str(p) for p in transcripts if p.exists()]
    if not files:
        return
    st = viewer.stream(f"pkg:{pkg}", files)
    looks = pkg / "looks"
    looks.mkdir(exist_ok=True)
    n = sum(len(viewer._cache[f]["images"]) for f in files)
    exts = []
    for i in range(n):
        im = viewer.image(st, i)
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(im[0], "bin") if im else "bin"
        exts.append(ext)
        if im:
            (looks / f"{i}.{ext}").write_bytes(base64.b64decode(im[1]))
    (pkg / "timeline.json").write_text(json.dumps({"events": st["events"], "imgext": exts}))


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
    """Tails a sitting's transcript: the live white-room audit (NFR-10) and the context threshold (RUN-7).
    It fails closed: a line it can't check, or a transcript that never appears, is a hit (QA Q6)."""

    def __init__(self, proc, transcript: Path, messages: set[str], config: Path, replies: Path):
        super().__init__(daemon=True)
        self.proc, self.path, self.messages, self.config = proc, transcript, messages, config
        self.replies = audit.Replies(replies)
        self.hits: list[str] = []
        self.context_end = False
        self.date_shown = None
        self.offset = 0
        self.started = time.time()
        self._stop = threading.Event()
        self._over = False

    def stop(self):
        self._stop.set()
        self.join(timeout=10)
        self.scan()  # whatever arrived last
        if not self.path.exists():
            self.hits.append("the sitting left no transcript where the audit looks for it")

    def run(self):
        while not self._stop.is_set():
            try:
                self.scan()
            except Exception as e:  # noqa: BLE001  (a watcher that dies would let everything through)
                self.hits.append(f"the audit failed: {type(e).__name__}: {e}")
                self.kill()
                return
            if not self.path.exists() and time.time() - self.started > TRANSCRIPT_GRACE and self.proc.poll() is None:
                self.hits.append("no transcript appeared to audit")
                self.kill()
                return
            self._stop.wait(1.0)

    def scan(self):
        if not self.path.exists():
            return
        with open(self.path, "rb") as fh:
            fh.seek(self.offset)
            data = fh.read()
        end = data.rfind(b"\n")
        if end < 0:
            return
        self.offset += end + 1
        stop = False
        for line in data[: end + 1].splitlines():  # every line is checked, even after a reason to stop (QA Q6)
            if not line.strip():
                continue
            hits = audit.check_entry(line, self.messages, self.config, self.replies)
            if hits:
                self.hits += hits
                stop = True
                continue
            d = json.loads(line)
            if d.get("type") == "attachment" and (d.get("attachment") or {}).get("type") == "date":
                m = re.search(r"\d{4}-\d{2}-\d{2}", "".join(x.get("content", "") for x in d.get("rendered") or []))
                self.date_shown = m.group(0) if m else None
            usage = (d.get("message") or {}).get("usage") if d.get("type") == "assistant" else None
            if usage:
                ctx = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                self._over = self._over or ctx > CONTEXT_LIMIT
            if self._over and d.get("type") == "user":  # right after a tool result: nothing half done
                self.context_end = True
                stop = True
        if stop:
            self.kill()

    def kill(self):
        if self.proc.poll() is None:
            threading.Thread(target=stop_group, args=(self.proc.pid,), daemon=True).start()


def stop_group(pgid: int):
    """SIGTERM to a process group, then SIGKILL if it is still there after KILL_GRACE (QA Q21)."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(KILL_GRACE):
        time.sleep(1)
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def claude_cmd(studio: Path, run: Path, message: str, sid: str, model: str, effort: str, replies: Path) -> list[str]:
    """Claude Code for one sitting, isolated (RUN-13, RUN-14); its MCP config is written to the run folder."""
    mcp = run / "mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"easel": {"command": str(NODE), "args": [str(EASEL_MCP), str(studio), str(replies)]}}}))
    return [str(CLAUDE), "-p", message, "--session-id", sid, "--model", model, "--effort", effort,
            "--system-prompt", (TEXTS / "system_prompt.md").read_text().strip(),
            "--tools", "", "--allowedTools", ",".join(f"mcp__easel__{t}" for t in TOOLS),
            "--strict-mcp-config", "--mcp-config", str(mcp),
            "--setting-sources", "", "--settings", str(TEXTS / "settings.json"),
            "--disable-slash-commands", "--thinking-display", "summarized",
            "--output-format", "stream-json", "--verbose"]


def whiteroom(artist: Artist) -> list[str]:
    """NFR-9: the prepared studio, the messages and the system prompt. Our texts get the full word list; the
    artist's own (notebook, toolkit, its wall cards and the index made from its titles) only private words (QA Q5)."""
    ours = {"BRIEF.md", "notes/easel_guide.md", "notes/research/oil_paint_physics.md", "notes/journal.md"}
    hits = audit.scan_studio(artist.studio, ours)
    for name, text in messages().items():
        hits += audit.scan_text(f"messages.{name}", text, True)
    hits += audit.scan_text("system_prompt", (TEXTS / "system_prompt.md").read_text(), True)
    return hits


def a_model(a: Artist) -> str:
    return json.loads((a.home / "birth.json").read_text())["model"]


def a_effort(a: Artist) -> str:
    return json.loads((a.home / "birth.json").read_text())["effort"]


def model_seen(sittings: list[dict]) -> list[str]:
    seen = []
    for rec in sittings:
        p = Path(rec["transcript"])
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            try:
                m = (json.loads(line).get("message") or {}).get("model")
            except (ValueError, AttributeError):
                continue
            if m and m.startswith("claude-") and m not in seen:
                seen.append(m)
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
            if isinstance(d, dict) and d.get("type") == "result":
                res = d
    return res


# a usage limit, not a transient rate limit (a 429 is a crash: retried soon, QA Q10)
LIMIT_RE = re.compile(r"(session|weekly|usage|5-hour|opus) limit|limit reached", re.I)


def is_limit(text: str) -> bool:
    return bool(LIMIT_RE.search(text))


def reset_time(text: str, now_: datetime | None = None) -> float | None:
    """The epoch of "resets 3pm" / "resets 3:30pm" / "resets Mon 9am" in a limit message (local time), or None.
    A time up to two hours past (the message read just after the hour) means "now", not a day or a week later."""
    m = re.search(r"resets?\s+(?:at\s+)?(?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)", text, re.I)
    if not m:
        return None
    ref = now_ or datetime.now()
    day, h, mi, ap = m.group(1), int(m.group(2)) % 12, int(m.group(3) or 0), m.group(4).lower()
    h += 12 if ap == "pm" else 0
    t = ref.replace(hour=h, minute=mi, second=0, microsecond=0)
    if day:
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        t += timedelta(days=(days.index(day.lower()[:3]) - t.weekday()) % 7)
    if timedelta(0) <= ref - t <= timedelta(hours=2):
        return ref.timestamp() + 60
    while t <= ref:
        t += timedelta(days=7 if day else 1)
    return t.timestamp() + 60  # a minute's grace
