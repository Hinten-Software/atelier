#!/usr/bin/env python3
"""The watcher's planned end of a sitting (window, budget, context): only once every tool call the model sent has
its result, and Claude Code's "Connection closed" for a call the stop cut off is not an audit hit then, but is one
at any other time (i-014, 2026-11-23: a look sent along with a paint; the window closed during the paint).

    python3 runner/tests/test_watcher.py
"""
import json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="atelier-watcher-"))
os.environ |= {"ATELIER_DATA": str(TMP / "data"), "ATELIER_SECRETS": str(TMP / "secrets"), "ATELIER_WINDOW": "always"}
sys.path.insert(0, str(HERE.parent))
import works  # noqa: E402

failed = 0


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


class Proc:
    pid = 0

    def poll(self):
        return None


def watcher(name):
    w = works.Watcher(Proc(), TMP / f"{name}.jsonl", set(), TMP / "config", TMP / f"{name}.replies.jsonl")
    w.killed = 0
    w.kill = lambda: setattr(w, "killed", w.killed + 1)
    return w


def put(w, *lines):
    with open(w.path, "a") as f:
        for d in lines:
            f.write(json.dumps(d) + "\n")
    w.scan()


def calls(*ids):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": i, "name": "mcp__easel__paint", "input": {}} for i in ids]}}


def result(w, id, text):
    with open(w.replies.path, "a") as f:
        f.write(json.dumps({"text": [text], "error": False}) + "\n")
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": id, "content": [{"type": "text", "text": text}]}]}}


def closed(id):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": id, "content": "Connection closed", "is_error": True}]}}


# two calls sent together; the window closes while the first runs
w = watcher("pair")
put(w, calls("a", "b"))
w.budget_end = "window"
put(w, result(w, "a", "day 1, 09:10\nok"))
check("a call still waiting holds the planned end back", w.killed == 0 and not w.hits, (w.killed, w.hits))
put(w, result(w, "b", "look"))
check("the end comes once every call has its result", w.killed == 1 and not w.hits, (w.killed, w.hits))

# the model sends another call between the last result and the stop: Claude Code closes the easel under it
put(w, calls("c"), closed("c"))
check("'Connection closed' after our own stop is no hit", not w.hits, w.hits)
put(w, {"type": "user", "message": {"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "c", "content": "something else", "is_error": True}]}})
check("any other foreign result after our stop still is", len(w.hits) == 1, w.hits)

# one call at a time: the end comes right after its result, as before
w = watcher("single")
put(w, calls("a"))
w.budget_end = "daily"
put(w, result(w, "a", "ok"))
check("a single call's result ends the sitting", w.killed == 1 and not w.hits, (w.killed, w.hits))

# without a stop of ours, a closed connection is a hit
w = watcher("unplanned")
put(w, calls("a"), closed("a"))
check("'Connection closed' with no stop of ours is a hit", len(w.hits) == 1 and w.killed == 1, (w.hits, w.killed))

print("FAILED" if failed else "all ok")
sys.exit(1 if failed else 0)
