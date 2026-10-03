#!/usr/bin/env python3
"""A stand-in for Claude Code in the runner's tests: one sitting, acted out as the config dir's `fake-modes` file
says (one mode a line, consumed one per sitting). It writes a transcript the way Claude Code does, paints through
the studio's real easel, and ends the way the mode says:

  voluntary  paints, then ends with a reply (the artist stops)
  crash      exits 1
  limit      ends with a usage-limit error
  context    reports a huge context, then waits to be stopped
  leak       shows the model a "say what you're doing" reminder (NFR-10 must stop it)
  email      a tool result holding an email address (NFR-10 must stop it)
  notebook   writes notebook.md, then leaks (the rollback must restore notebook.md)
"""
import json, os, re, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

args = sys.argv[1:]
message = args[args.index("-p") + 1]
sid = args[args.index("--session-id") + 1]
config = Path(os.environ["CLAUDE_CONFIG_DIR"])
cwd = Path.cwd()
modes_file = config / "fake-modes"
modes = modes_file.read_text().split()
mode, rest = modes[0], modes[1:]
modes_file.write_text("\n".join(rest))
tr = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd)) / f"{sid}.jsonl"
tr.parent.mkdir(parents=True, exist_ok=True)
ts = lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def put(d):
    d.setdefault("timestamp", ts()); d.setdefault("sessionId", sid); d.setdefault("cwd", str(cwd))
    with open(tr, "a") as f:
        f.write(json.dumps(d) + "\n")
def attach(kind, text):
    put({"type": "attachment", "attachment": {"type": kind}, "rendered": [{"content": text}]})
def say_out(d):
    print(json.dumps(d), flush=True)

put({"type": "user", "message": {"role": "user", "content": message}})
attach("environment", f"<system-reminder>\n# Environment\nYou have been invoked in the following environment: \n - Primary working directory: {cwd}\n - Is a git repository: false\n - Platform: darwin\n - Shell: unknown\n - OS Version: Darwin 27.0.0\n</system-reminder>")
attach("model", "<system-reminder>\nYou are powered by the model named Opus 5.5. The exact model ID is claude-opus-5-5. Assistant knowledge cutoff is June 2026.\n</system-reminder>")
attach("date", f"<system-reminder>\nToday's date is {datetime.now():%Y-%m-%d}.\n</system-reminder>")
attach("session_context", "")
def easel(*a, stdin=""):
    return subprocess.run([str(cwd / "bin" / "easel"), *a], cwd=cwd, input=stdin, capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]}).stdout
def tool(name, inp, out):
    tid = "toolu_" + uuid.uuid4().hex[:20]
    put({"type": "assistant", "message": {"model": "claude-opus-5-5", "id": "msg_" + uuid.uuid4().hex[:8], "role": "assistant",
         "content": [{"type": "tool_use", "id": tid, "name": f"mcp__easel__{name}", "input": inp}],
         "usage": {"input_tokens": 5, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 9000, "output_tokens": 50}}})
    put({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": [{"type": "text", "text": out}]}]}})

if not (cwd / "paintings/lua/painting.lua").exists():
    easel("open")
    chunk = 'canvas{size=300, aspect=1.25, linen=18, seed=7, ground={{pile={{"lead white", 3}, {"yellow ochre", 1}}, um=60, apply="knife", texture=0.3}}}'
    tool("paint", {"lua": chunk}, easel("do", "-", stdin=chunk))
chunk = 'p = pile{{"Prussian blue", 1}, {"lead white", 4}}\nwork(rect(100, 100, 300, 200), {hand="body", pile=p, coverage=1})'
tool("paint", {"lua": chunk}, easel("do", "-", stdin=chunk))

if mode == "voluntary":
    reply = "I've finished the study and called it **Test Study**.\n\nA band of blue on a warm ground."
    put({"type": "assistant", "message": {"model": "claude-opus-5-5", "id": "msg_end", "role": "assistant", "content": [{"type": "text", "text": reply}]}})
    say_out({"type": "result", "subtype": "success", "is_error": False, "result": reply})
elif mode == "crash":
    print("fake: something broke", file=sys.stderr); sys.exit(1)
elif mode == "limit":
    say_out({"type": "result", "subtype": "success", "is_error": True, "result": "You've hit your session limit"}); sys.exit(1)
elif mode == "context":
    put({"type": "assistant", "message": {"model": "claude-opus-5-5", "id": "msg_big", "role": "assistant", "content": [{"type": "text", "text": "…"}],
         "usage": {"input_tokens": 5, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 700000, "output_tokens": 5}}})
    tool("status", {}, easel("status"))
    time.sleep(60)
elif mode in ("leak", "notebook"):
    if mode == "notebook":
        (cwd / "notebook.md").write_text("written during a sitting that will be rolled back\n")
    attach("silent_turn_reminder", "<system-reminder>\nThe user hasn't heard from you in a while — say in a few words what you're doing, then continue.\n</system-reminder>")
    time.sleep(60)
elif mode == "email":
    tool("read", {"path": "notes/x"}, "contact: someone@example.com")
    time.sleep(60)
