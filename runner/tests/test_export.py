#!/usr/bin/env python3
"""The export (REC-3, REC-7, REC-8): a clean work is published; a leak blocks the export and leaves the published
site as it was; the block report never repeats the private text; contaminated works stay private.

    python3 runner/tests/test_export.py
"""
import base64, json, os, shutil, subprocess, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(f"/Users/Shared/atelier/x{os.getpid() % 10000}")
ENV = os.environ | {"ATELIER_DATA": str(DATA), "ATELIER_SECRETS": str(DATA / "secrets")}
failed = 0
PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                     "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


def transcript(path: Path, extra_text=""):
    sid, cwd = path.stem, "/Users/Shared/zz/studio"
    lines = [
        {"type": "user", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-03T10:00:00Z", "message": {"role": "user", "content": "Your brief is in BRIEF.md in this folder."}},
        {"type": "assistant", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-03T10:00:01Z", "message": {"role": "assistant", "model": "claude-opus-5-5", "content": [
            {"type": "thinking", "thinking": "A pear, I think." + extra_text}, {"type": "tool_use", "id": "t1", "name": "mcp__easel__look", "input": {}}]}},
        {"type": "user", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-03T10:00:02Z", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [
                {"type": "text", "text": f"{cwd}/out/easel/painting/{uuid.uuid4()}.png (1000x800)"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG}},
                {"type": "text", "text": f"[Image: source: /Users/Shared/zz/.config/projects/x/{sid}/images/1.png]"}]}]}},
        {"type": "assistant", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-03T10:00:03Z", "message": {"role": "assistant", "model": "claude-opus-5-5", "content": [
            {"type": "text", "text": "I've finished and called it **Pear**."}]}},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def work(id, contaminated=False, extra=""):
    sid = str(uuid.uuid4())
    tr = DATA / "tr" / f"{sid}.jsonl"
    transcript(tr, extra)
    (DATA / "run" / id).mkdir(parents=True, exist_ok=True)
    (DATA / "works" / id).mkdir(parents=True, exist_ok=True)
    (DATA / "run" / id / "state.json").write_text(json.dumps({"number": int(id[-3:]), "mode": "free", "theme": None, "created": "x",
        "state": "finished", "contaminated": contaminated, "sittings": [{"n": 1, "session": sid, "transcript": str(tr)}]}))
    (DATA / "works" / id / "manifest.json").write_text(json.dumps({"id": id, "title": "Pear", "finished": True, "contaminated": contaminated}))
    (DATA / "works" / id / "painting.lua").write_text("--@ chunk\ncanvas{}\n")
    return tr


def export():
    return subprocess.run(["/opt/homebrew/bin/uv", "run", "-q", "--with", "pillow", "python3", str(HERE.parent / "export.py")],
                          env=ENV, capture_output=True, text=True)


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    try:
        work("i-001")
        work("i-002", contaminated=True)
        r = export()
        site = DATA / "site"
        check("a clean export publishes", r.returncode == 0 and (site / "studio/data/w-i-001/events.json").exists(), r.stderr[-300:])
        check("contaminated work withheld", not (site / "studio/data/w-i-002").exists())
        ev = (site / "studio/data/w-i-001/events.json").read_text()
        check("no studio path, no image-source note", "/Users/" not in ev and "Image: source" not in ev, ev[:300])
        check("no dot-files published", not any(p.name.startswith(".") for p in site.rglob("*")))
        check("works.json lists the clean work only", [w["id"] for w in json.loads((site / "data/works.json").read_text())["works"]] == ["i-001"])
        before = (site / "studio/data/w-i-001/events.json").read_text()
        work("i-003", extra=" Write to someone@example.com.")
        r = export()
        check("a leak blocks the export", r.returncode == 2, r.returncode)
        check("the published site is unchanged", not (site / "studio/data/w-i-003").exists()
              and (site / "studio/data/w-i-001/events.json").read_text() == before)
        report = (DATA / "run/export-blocked.txt").read_text()
        check("the block report names the problem, not the text", "email" in report and "example.com" not in report, report)
        check("nothing blocked is under the site", not (site / ".blocked").exists())
    finally:
        shutil.rmtree(DATA, ignore_errors=True)
    print("all passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
