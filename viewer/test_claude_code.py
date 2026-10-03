#!/usr/bin/env python3
"""The viewer's Claude Code branches (the atelier): a transcript parses into claude-paint's events, the picker finds
its look and title, and Claude Code's image-source notes never reach the timeline.

    python3 viewer/test_claude_code.py
"""
import base64, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio as S

PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                     "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()
failed = 0


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


lines = [
    {"type": "user", "sessionId": "s", "cwd": "/Users/Shared/zz/studio", "timestamp": "t0", "message": {"role": "user", "content": "Your brief is in BRIEF.md in this folder."}},
    {"type": "attachment", "sessionId": "s", "attachment": {"type": "date"}, "rendered": [{"content": "x"}]},
    {"type": "assistant", "sessionId": "s", "timestamp": "t1", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "a pear"}]}},
    {"type": "assistant", "sessionId": "s", "timestamp": "t1", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "a", "name": "mcp__easel__paint", "input": {"lua": "canvas{}"}}]}},
    {"type": "user", "sessionId": "s", "timestamp": "t2", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": "ok"}]}]}},
    {"type": "assistant", "sessionId": "s", "timestamp": "t3", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "b", "name": "mcp__easel__look", "input": {}}]}},
    {"type": "user", "sessionId": "s", "timestamp": "t4", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "b", "content": [
        {"type": "text", "text": "studio/out/x.png (1000x800)"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG}},
        {"type": "text", "text": "[Image: source: /Users/Shared/zz/.config/projects/p/s/images/1.png]"}]}]}},
    {"type": "assistant", "sessionId": "s", "timestamp": "t5", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "c", "name": "mcp__easel__note", "input": {"text": "warm ground"}}]}},
    {"type": "user", "sessionId": "s", "timestamp": "t6", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c", "content": "a crop may be at most 500 units", "is_error": True}]}},
    {"type": "assistant", "sessionId": "s", "timestamp": "t7", "message": {"role": "assistant", "content": [{"type": "text", "text": "I've finished and titled it **Pear at Dusk**.\n\n**Note:** the light."}]}},
]
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
    fh.write("\n".join(json.dumps(l) for l in lines) + "\n")
ev, im = S.parse(fh.name)
kinds = [e["kind"] for e in ev]
check("events", kinds == ["start", "user", "think", "paint", "look", "image", "jnote", "say"], kinds)
check("one image", len(im) == 1)
look = next(e for e in ev if e["kind"] == "look")
check("image-source note dropped", "Image: source" not in look.get("out", ""), look.get("out"))
check("error result marked", next(e for e in ev if e["kind"] == "jnote").get("err") is True)
g = S.glance([fh.name])
check("picker look and title", g["look"] == 0 and g["title"] == "Pear at Dusk", g)
check("a label is not a title", S.title_of("**Note:** the light.") is None)
os.unlink(fh.name)
print("all passed" if not failed else f"{failed} failed")
sys.exit(1 if failed else 0)
