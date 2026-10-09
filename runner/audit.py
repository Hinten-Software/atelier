"""The white room, checked (requirements 3.2, NFR-9, NFR-10).

NFR-9: before a work starts, everything we put in front of the artist (the prepared studio's notes, the brief,
the messages, the tool descriptions) is scanned with tools/whiteroom.py's word list; the artist's own files
(notebook, toolkit, wall cards) only for private words, since the artist may write any word it likes.

NFR-10: during a sitting, every transcript line Claude Code writes is checked against the accepted signals
(section 3.2). Anything else that reaches the model, or any private word, the account's email, a token counter
or a "say what you're doing" nudge, is a hit: the runner stops the sitting.
"""
import json
import re
import sys
from pathlib import Path

from config import NOTES, PRIVATE_WORDS, REPO

sys.path.insert(0, str(REPO / "tools"))
import whiteroom  # noqa: E402  (its WORDS already include the private list)

if not PRIVATE_WORDS.exists():  # without it the checks would pass everything (QA Q18)
    raise SystemExit(f"audit: no private word list at {PRIVATE_WORDS} (requirements REC-7); refusing to run")
PRIVATE = [w.strip() for w in PRIVATE_WORDS.read_text().splitlines() if w.strip() and not w.startswith("#")]
PRIVATE_RE = re.compile("|".join(PRIVATE), re.I) if PRIVATE else None
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
HOME_RE = re.compile(r"/Users/(?!Shared/)[^/\s]+")

# what Claude Code may show the model, by attachment type: a pattern its rendered text must match ("" = must be empty)
ACCEPTED = {
    "environment": re.compile(r"(?s)^<system-reminder>\n# Environment\nYou have been invoked in the following environment: \n"
                              r" - Primary working directory: /Users/Shared/[a-z0-9]+/studio\n - Is a git repository: false\n"
                              r" - Platform: darwin\n - Shell: [\w./-]+\n - OS Version: [\w. ]+\n</system-reminder>$"),
    "model": re.compile(r"(?s)^<system-reminder>\nYou are powered by the model named [\w. ]+\. The exact model ID is "
                        r"[\w-]+\. Assistant knowledge cutoff is \w+ \d{4}\.\n</system-reminder>$"),
    "date": re.compile(r"^<system-reminder>\nToday's date is \d{4}-\d{2}-\d{2}\.\n</system-reminder>$"),
    "session_context": "", "credential_org": "", "prompt_snapshot": "", "thinking_drop": "",
}


def private_hits(text: str) -> list[str]:
    hits = []
    if PRIVATE_RE and (m := PRIVATE_RE.search(text)):
        hits.append(f"private word {m.group(0)!r}")
    if m := EMAIL_RE.search(text):
        hits.append(f"an email address {m.group(0)!r}")
    if m := HOME_RE.search(text):
        hits.append(f"a home path {m.group(0)!r}")
    return hits


# the studio's names for the repository's texts (config.NOTES): "easel guide" is materials/easel_guide.md
SOURCE_NAMES = {dst: src for src, dst in NOTES.items()}


def scan_text(name: str, text: str, ours: bool) -> list[str]:
    """NFR-9 for one text the artist will read. ours: we wrote it (full word list), else the artist did (private words)."""
    found = [f"{name}: {h}" for h in private_hits(text)]
    if ours:
        for n, line in enumerate(text.splitlines(), 1):
            for m in whiteroom.PATTERN.finditer(line):
                src = SOURCE_NAMES.get(name, name)  # a text in the studio is allowed what its source in the repository is
                allowed = any(src.endswith(sfx) and sub in line for (sfx, sub) in whiteroom.ALLOW)
                if not allowed:
                    found.append(f"{name}:{n}: {m.group(0)!r} in {line.strip()[:100]!r}")
    return found


def scan_studio(studio: Path, ours: set[str]) -> list[str]:
    """NFR-9 over every file the artist can read in the prepared studio (bin/ and out/ are hidden from it)."""
    found = []
    for f in sorted(studio.rglob("*")):
        rel = f.relative_to(studio)
        if not f.is_file() or rel.parts[0] in ("bin", "out", "paintings") or any(p.startswith(".") for p in rel.parts):
            continue
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") or b"\0" in f.read_bytes()[:8192]:
            continue  # the paintings on the walls (named without an extension) are images
        found += scan_text(str(rel), f.read_text(errors="replace"), str(rel) in ours)
    return found


def _rendered(d: dict) -> str:
    return "".join(x.get("content", "") for x in d.get("rendered") or [])


class Replies:
    """What the easel's MCP server sent (its reply log, one JSON line a reply). Every tool result in the transcript
    must be one of these, exactly; anything else reached the model from somewhere else (QA Q3, Q4, Q7)."""

    def __init__(self, path: Path | None):
        self.path, self.offset, self.unmatched = path, 0, []

    def _load(self):
        if not self.path or not self.path.exists():
            return
        with open(self.path, "rb") as fh:
            fh.seek(self.offset)
            data = fh.read()
        end = data.rfind(b"\n")
        if end >= 0:
            self.offset += end + 1
            self.unmatched += [json.loads(l)["text"] for l in data[: end + 1].splitlines() if l.strip()]

    def take(self, texts: list[str]) -> bool:
        self._load()
        for i, r in enumerate(self.unmatched):
            if r == texts:
                del self.unmatched[i]
                return True
        return False


# the easel's own answer to a call with a missing or mistyped argument: its MCP server checks the arguments against
# the tool's schema before the tool runs, so the reply never reaches the replies log (ii-002, 2026-10-07: an `edit`
# without `text`). The easel's eight tools only; anything else in that form is still a hit.
OWN_ARGUMENT_ERROR = re.compile(r"MCP error -32602: Input validation error: Invalid arguments for tool "
                                r"(paint|look|note|status|log|read|write|edit): [^\n]{0,600}", re.S)


def _tool_result(x: dict, config_dir: Path, replies: Replies | None) -> list[str]:
    parts = x.get("content")
    if isinstance(parts, str):
        texts = [parts]
    else:
        texts, hits = [], []
        for p in parts or []:
            if p.get("type") == "text":
                text = p.get("text", "")
                if text.startswith("[Image: source: "):  # Claude Code's note of where it saved an image
                    if not text.startswith(f"[Image: source: {config_dir}/"):
                        return [f"image note outside the artist's config: {text[:200]!r}"]
                    continue
                texts.append(text)
            elif p.get("type") != "image":
                return [f"a {p.get('type')!r} part in a tool result"]
    hits = [h for t in texts for h in private_hits(t)]
    if replies is not None and not (OWN_ARGUMENT_ERROR.fullmatch(" ".join(texts)) or replies.take(texts)):
        hits.append(f"a tool result the easel didn't send: {' | '.join(texts)[:300]!r}")
    return hits


def check_line(d: dict, messages: set[str], config_dir: Path, replies: Replies | None = None) -> list[str]:
    """NFR-10 for one transcript line: the reasons it is a hit (empty if it is accepted). Anything that isn't in
    the accepted signals (requirements 3.2) is a hit: unknown kinds of entries and attachments included."""
    t = d.get("type")
    if t == "attachment":
        att = d.get("attachment")
        if not isinstance(att, dict):
            return [f"an attachment of unexpected shape: {json.dumps(d)[:200]}"]
        kind = att.get("type")
        text = _rendered(d)
        hits = [f"attachment {kind!r}: {h}" for h in private_hits(json.dumps(att) + text)]
        want = ACCEPTED.get(kind)
        if want is None:
            return hits + [f"unknown attachment {kind!r}: {(text or json.dumps(att))[:200]!r}"]
        if want == "":
            return hits + ([f"attachment {kind!r} is not empty: {text[:200]!r}"] if text.strip() else [])
        return hits + ([] if want.match(text) else [f"attachment {kind!r} differs from the accepted form: {text[:300]!r}"])
    if t == "system":
        sub = d.get("subtype", "")
        if "compact" in sub:
            return [f"compaction ({sub}) though it is off"]
        return [f"system entry: {h}" for h in private_hits(json.dumps(d))]
    if t == "user":
        content = (d.get("message") or {}).get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        hits = []
        for x in content or []:
            if not isinstance(x, dict):
                hits.append(f"a user entry of unexpected shape: {json.dumps(x)[:200]}")
            elif x.get("type") == "text":
                text = x.get("text", "")
                if text.startswith("[Image: source: "):  # Claude Code's note of where it saved an image
                    if not text.startswith(f"[Image: source: {config_dir}/"):
                        hits.append(f"image note outside the artist's config: {text[:200]!r}")
                elif text.startswith("Your response above was stopped by a safety classifier"):
                    hits.append(f"a safety classifier's notice reached the model: {text[:200]!r}")
                elif text.strip() and text not in messages:
                    hits.append(f"text the runner didn't send: {text[:300]!r}")
            elif x.get("type") == "tool_result":
                hits += _tool_result(x, config_dir, replies)
            else:
                hits.append(f"a {x.get('type')!r} entry in a user turn")
        return hits
    if t == "assistant":
        return []  # the artist's own words
    return []  # bookkeeping entries (queue, titles, cost): not sent to the model


def check_transcript(path: Path, messages: set[str], config_dir: Path, replies: Path | None = None) -> list[str]:
    book = Replies(replies) if replies else None
    hits = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        hits += [f"line {n}: {h}" for h in check_entry(line, messages, config_dir, book)]
    return hits


def check_entry(line: bytes | str, messages: set[str], config_dir: Path, replies: Replies | None) -> list[str]:
    """check_line for one raw transcript line; a line that can't be read or checked is a hit, never a pass (QA Q6)."""
    try:
        d = json.loads(line)
        if not isinstance(d, dict):
            raise ValueError("not an object")
        return check_line(d, messages, config_dir, replies)
    except Exception as e:  # noqa: BLE001
        return [f"a transcript entry that couldn't be checked ({type(e).__name__}): {str(line)[:200]}"]


if __name__ == "__main__":  # audit transcripts by hand: audit.py <config dir> <transcript.jsonl>...
    msgs = set(json.loads((REPO / "runner" / "texts" / "messages.json").read_text()).values())
    for p in sys.argv[2:]:
        for h in check_transcript(Path(p), msgs, Path(sys.argv[1])):
            print(h)
