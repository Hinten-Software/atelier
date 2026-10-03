# /// script
# requires-python = ">=3.11"
# ///
"""M0 spike: one sitting of a throwaway test painter in Claude Code, headless, isolated.

    uv run spike/run_sitting.py new [--max-turns N] [--model M] [--effort E]   # fresh studio, first sitting
    uv run spike/run_sitting.py again <studio> [--max-turns N] ...             # another sitting, fresh session

The painter is no artist of the atelier: its studio lives under /Users/Shared/atelier/spike and
is thrown away. Claude Code runs as shipped, logged in to the subscription in its own config dir
(~/.atelier/claude), with no built-in tools, no user or project settings, no CLAUDE.md, no
memory, no slash commands and only the easel's MCP server.
"""
import argparse, json, os, re, secrets, shutil, subprocess, sys, time, uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPIKE = Path(__file__).resolve().parent
ROOT = Path("/Users/Shared/atelier/spike")  # short: the easel's Unix socket path must stay under 104 bytes
CLAUDE = Path.home() / ".local/bin/claude"
NODE = shutil.which("node") or "/opt/homebrew/bin/node"
CONFIG = Path.home() / ".atelier/claude"
TOOLS = ["paint", "look", "note", "status", "log", "read"]
FIRST = "Your brief is in BRIEF.md in this folder."
AGAIN = "You're back at the easel. The painting is as you left it. Your brief is in BRIEF.md and your journal in notes/journal.md."


def strip_comments(text):
    """A note as the artist reads it: without HTML comments (the physics note's first line is a canary comment
    naming a benchmark and a gallery; requirements NFR-9)."""
    return re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)


def new_studio():
    s = ROOT / f"studio-{secrets.token_hex(3)}"
    (s / "bin").mkdir(parents=True)
    (s / "notes/research").mkdir(parents=True)
    (s / "paintings/lua").mkdir(parents=True)
    shutil.copy2(REPO / "engine/target/painter/release/easel", s / "bin/easel")
    for src, dst in (("easel_guide.md", "easel_guide.md"), ("research/oil_paint_physics.md", "research/oil_paint_physics.md")):
        (s / "notes" / dst).write_text(strip_comments((REPO / "materials" / src).read_text()))
    shutil.copy2(SPIKE / "BRIEF.md", s / "BRIEF.md")
    (s / "notes/journal.md").write_text("")
    return s


def sitting(studio: Path, message: str, a):
    run = studio.parent / (studio.name + "-run")  # outside the studio: the painter never sees it
    run.mkdir(exist_ok=True)
    sid = str(uuid.uuid4())
    mcp = {"mcpServers": {"easel": {"command": NODE, "args": [str(REPO / "easel-mcp/src/server.ts"), str(studio)]}}}
    (run / "mcp.json").write_text(json.dumps(mcp))
    cmd = [str(CLAUDE), "-p", message,
           "--session-id", sid,
           "--model", a.model, "--effort", a.effort,
           "--system-prompt", (SPIKE / "system_prompt.md").read_text().strip(),
           "--tools", "",
           "--allowedTools", ",".join(f"mcp__easel__{t}" for t in TOOLS),
           "--strict-mcp-config", "--mcp-config", str(run / "mcp.json"),
           "--setting-sources", "", "--settings", str(SPIKE / "settings.json"),
           "--disable-slash-commands",
           "--output-format", "stream-json", "--verbose"]
    if a.max_turns:
        cmd += ["--max-turns", str(a.max_turns)]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LANG": "en_US.UTF-8",
           "CLAUDE_CONFIG_DIR": str(CONFIG),
           "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"}
    t0 = time.time()
    print(f"sitting: studio {studio}, session {sid}", flush=True)
    with open(run / f"{sid}.stream.jsonl", "w") as out, open(run / f"{sid}.stderr.txt", "w") as err:
        rc = subprocess.run(cmd, cwd=studio, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err).returncode
    rec = {"session": sid, "exit": rc, "seconds": round(time.time() - t0), "message": message,
           "model": a.model, "effort": a.effort, "max_turns": a.max_turns,
           "started": time.strftime("%F %T", time.localtime(t0))}
    with open(run / "sittings.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    return rc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["new", "again"])
    p.add_argument("studio", nargs="?")
    p.add_argument("--max-turns", type=int, default=0)
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default="high")
    a = p.parse_args()
    if a.what == "new":
        sys.exit(sitting(new_studio(), FIRST, a))
    sys.exit(sitting(Path(a.studio), AGAIN, a))


if __name__ == "__main__":
    main()
