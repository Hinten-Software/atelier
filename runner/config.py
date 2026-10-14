"""Where the atelier keeps things, and the fixed parts of an artist's setup (requirements sections 5, 7)."""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEXTS = REPO / "runner" / "texts"

# the private store (mode 700): artists' records, works, run state, the pinned harness; synced to the NAS
DATA = Path(os.environ.get("ATELIER_DATA", Path.home() / "atelier-data"))
# where the export builds and keeps the site: the store itself, unless ATELIER_WORK names another folder
WORK = Path(os.environ.get("ATELIER_WORK", DATA))
# artists' roots live here, outside every home folder, so no account name is in any path an artist sees (ENG-7)
ROOTS = Path(os.environ.get("ATELIER_ROOTS", "/Users/Shared"))

CLAUDE_VERSION = os.environ.get("ATELIER_CLAUDE_VERSION", "2.1.288")
# pinned copy, never the auto-updating install (RUN-15); ATELIER_CLAUDE: tests only (tests/fake_claude.py)
CLAUDE = Path(os.environ.get("ATELIER_CLAUDE", DATA / "bin" / f"claude-{CLAUDE_VERSION}"))
# secrets live outside the store: the store is backed up to the NAS, a secret never is
SECRETS = Path(os.environ.get("ATELIER_SECRETS", Path.home() / ".atelier" / "secrets"))
TOKEN = SECRETS / "claude-oauth-token"  # `claude setup-token`, written by the owner (RUN-13)
NODE = Path(os.environ.get("ATELIER_NODE", "/opt/homebrew/bin/node"))
EASEL_MCP = REPO / "easel-mcp" / "src" / "server.ts"
# a painter's easel per box (tools/build-engine.sh): a studio gets its work's box's, nothing that names another box
PAINTER_BOXES = REPO / "engine" / "target" / "painter" / "boxes"
DEFAULT_BOX = "every"  # every tube (the owner, 2026-10-07); a work may be given another box (atelier paint --box)


def painter_easel(box: str = DEFAULT_BOX) -> Path:
    return PAINTER_BOXES / box / "easel"


def boxes() -> list[str]:
    """The boxes a work can be given: those built (tools/build-engine.sh), every box the easel has."""
    return sorted(d.name for d in PAINTER_BOXES.glob("*") if (d / "easel").exists())


PAINTER_EASEL = painter_easel()  # the default box's (the probes' fingerprint)
REPLAY_EASEL = REPO / "engine" / "target" / "release" / "easel"
CHECK_PAINTING = REPO / "engine" / "scripts" / "check_painting"
MATERIALS = REPO / "materials"
# the studio names things as a painter would (owner, 2026-10-06): no file names with extensions
NOTES = {"easel_guide.md": "easel guide", "research/oil_paint_physics.md": "notes on oil paint"}
PRIVATE_WORDS = Path(os.environ.get("ATELIER_PRIVATE_WORDS", Path.home() / ".atelier" / "private-words.txt"))

MODEL = "claude-opus-5-5"
EFFORT = "high"
TOOLS = ["paint", "look", "note", "status", "log", "read", "write", "edit"]

CONTEXT_LIMIT = 600_000          # tokens: a sitting ends after the tool result that passes it (RUN-7)
_SCALE = float(os.environ.get("ATELIER_WAIT_SCALE", "1"))  # tests only: shorter waits
CRASH_WAITS = [w * _SCALE for w in (90, 180, 300, 600, 900, 1200)]  # seconds before the sitting after the 1st, 2nd, ... crash
LIMIT_RETRY_S = 30 * 60 * _SCALE  # a usage limit without a reset time: try again this often (RUN-6)
LIMIT_GIVE_UP_S = 7 * 24 * 3600  # ... and stop after this long (not-finished)
MAX_INVOLUNTARY = 12             # involuntary ends of one work before it stops as not-finished


def artist_env(config_dir: Path, root: Path | None = None) -> dict:
    """The environment Claude Code runs in for an artist (RUN-13): nothing from the operator's shell. With the
    token login, HOME is the artist's own root, not the operator's home (QA Q21)."""
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root) if (root and TOKEN.exists()) else str(Path.home()),
        "LANG": "en_US.UTF-8",
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_AUTO_COMPACT": "1",
        # "The user hasn't heard from you in a while - say in a few words what you're doing": a nudge to narrate
        "CLAUDE_CODE_SILENT_TURN_REMINDER": "0",
        # how long Claude Code waits for a tool: as long as the easel client may (easel-client.ts WAIT_MS: a chunk
        # 48 minutes, the easel's 40 at 4800 px and a fifth more; a painting's rebuild at a sitting's start up to 120
        # minutes without progress), and a little more. Claude Code also gives up on a tool that sends nothing for
        # 30 minutes, apart from the total: that too (2026-10-13: the long probe's chunk took 24-27; 2026-10-14: a
        # review found the 45 minutes set then shorter than a chunk's limit and the client's waits)
        "MCP_TOOL_TIMEOUT": str(125 * 60 * 1000),
        "CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT": str(125 * 60 * 1000),
        "MAX_MCP_OUTPUT_TOKENS": "40000",
    }
    if TOKEN.exists():
        env["CLAUDE_CODE_OAUTH_TOKEN"] = TOKEN.read_text().strip()
    else:
        # a keychain login for this config dir: found only with USER set and LOGNAME unset (spike section 2)
        env["USER"] = os.environ.get("USER", "")
    return env
