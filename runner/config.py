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
ROOTS = Path("/Users/Shared")

CLAUDE_VERSION = "2.1.288"
# pinned copy, never the auto-updating install (RUN-15); ATELIER_CLAUDE: tests only (tests/fake_claude.py)
CLAUDE = Path(os.environ.get("ATELIER_CLAUDE", DATA / "bin" / f"claude-{CLAUDE_VERSION}"))
# secrets live outside the store: the store is backed up to the NAS, a secret never is
SECRETS = Path(os.environ.get("ATELIER_SECRETS", Path.home() / ".atelier" / "secrets"))
TOKEN = SECRETS / "claude-oauth-token"  # `claude setup-token`, written by the owner (RUN-13)
NODE = Path("/opt/homebrew/bin/node")
EASEL_MCP = REPO / "easel-mcp" / "src" / "server.ts"
# a studio's bin/ per box (tools/build-engine.sh): the painter's easel, `studio` ("painter <box>") and `width`
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

# a painter on a local model (the owner, 2026-10-22): LM Studio's Anthropic-compatible server, on this Mac only. Such a
# painter lives in a private store of their own (tools/local.sh), never one that is pushed to the NAS (export.py)
LOCAL_URL = "http://localhost:1234"
LOCAL_OUTPUT = 8192              # tokens a local reply may take (Claude Code's own default, 32000, would crowd the context)
LOCAL_MIN_CONTEXT = 49152        # a smaller loaded context can't hold the tools, the brief, the easel guide and some painting
LOCAL_MAX_SITTINGS = 40          # a local work's ceiling (its sittings cost nothing, and most end on its small context)
LOCAL_UNPAINTED = 3              # local sittings that end before any paint, retried before the work is not finished
LOCAL_NOT_READY_RETRY_S = 10 * 60 * float(os.environ.get("ATELIER_WAIT_SCALE", "1"))  # LM Studio or the model not up


def local_context_limit(context: int) -> int:
    """A local sitting's RUN-7 threshold for the context the model is loaded with: room left past it for one more
    tool result (the easel guide, about 13k tokens, is the largest) and a reply."""
    return context - 13_000 - LOCAL_OUTPUT - 3_000


def local_ready(local: dict) -> int | str:
    """The context the local model is loaded with (tokens), or why it can't paint now: LM Studio's own API says."""
    import json
    import urllib.error
    import urllib.parse
    import urllib.request
    url = f"{local['url']}/api/v0/models/{urllib.parse.quote(local['model'])}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            m = json.load(r)
    except urllib.error.HTTPError as e:
        return f"LM Studio has no model {local['model']!r} (HTTP {e.code})"
    except Exception as e:  # noqa: BLE001
        return f"LM Studio isn't answering at {local['url']} ({type(e).__name__}: {e}); is its server on?"
    if m.get("type") != "vlm":  # `look` shows the painter the canvas as a picture: a text-only model would paint blind
        return f"{local['model']} can't see pictures (LM Studio lists it as {m.get('type')!r}, not 'vlm')"
    if m.get("state") != "loaded" or not m.get("loaded_context_length"):
        return f"{local['model']} isn't loaded in LM Studio (state: {m.get('state')})"
    if m["loaded_context_length"] < LOCAL_MIN_CONTEXT:
        return f"{local['model']} is loaded with {m['loaded_context_length']} tokens of context; a sitting needs {LOCAL_MIN_CONTEXT}"
    return m["loaded_context_length"]
_SCALE = float(os.environ.get("ATELIER_WAIT_SCALE", "1"))  # tests only: shorter waits
CRASH_WAITS = [w * _SCALE for w in (90, 180, 300, 600, 900, 1200)]  # seconds before the sitting after the 1st, 2nd, ... crash
LIMIT_RETRY_S = 30 * 60 * _SCALE  # a usage limit without a reset time: try again this often (RUN-6)
LIMIT_GIVE_UP_S = 7 * 24 * 3600  # ... and stop after this long (not-finished)
MAX_INVOLUNTARY = 12             # involuntary ends of one work before it stops as not-finished


def artist_env(config_dir: Path, root: Path | None = None, local: dict | None = None) -> dict:
    """The environment Claude Code runs in for an artist (RUN-13): nothing from the operator's shell. With the
    token login, HOME is the artist's own root, not the operator's home (QA Q21). local: the birth record's "local"
    ({"url", "model"}): every request goes to that server, the background ones too, and no login or token is given."""
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root) if (root and (TOKEN.exists() or local)) else str(Path.home()),
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
    if local:
        env.update({
            "ANTHROPIC_BASE_URL": local["url"],
            "ANTHROPIC_AUTH_TOKEN": "lmstudio",  # LM Studio's own placeholder: its server asks for none
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": local["model"],  # Claude Code's background requests: the same model
            "ANTHROPIC_SMALL_FAST_MODEL": local["model"],
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(LOCAL_OUTPUT),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",  # nothing to Anthropic: no telemetry, no update checks
            # and anything else bound outside this Mac goes to a proxy that isn't there: it fails, nothing leaves
            "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": "localhost,127.0.0.1",
        })
    elif TOKEN.exists():
        env["CLAUDE_CODE_OAUTH_TOKEN"] = TOKEN.read_text().strip()
    else:
        # a keychain login for this config dir: found only with USER set and LOGNAME unset (spike section 2)
        env["USER"] = os.environ.get("USER", "")
    return env
