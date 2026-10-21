# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The studio: watch a painter paint, live or replayed.

Reads a painter's Claude Code transcripts (<sessions>/<folder>/*.jsonl, one per sitting, stitched into
one timeline): every chunk it painted, every look (the transcript holds the image bytes it saw), its notes
and its words. Serves a page with the painting, its thinking and a timeline to scrub. Read-only: it never
touches the painter. The public site is its static export (export_static.py, run by runner/export.py).

    python3 viewer/studio.py --sessions ~/.atelier/claude/projects   # then open http://localhost:8765
    python3 viewer/studio.py --sessions ... --host "$(tailscale ip -4)"   # from your other devices
"""
import argparse
import base64
import glob
import http.server
import json
import os
import re
import threading
import urllib.parse
from datetime import datetime

SESSIONS = os.path.expanduser("~/.atelier/claude/projects")
# --public: painters only, nothing that names this machine's owner (for a link shown to others)
PUBLIC = False
# the home folder whose path and account name are scrubbed: this machine's, or the painter's when the export runs
# elsewhere (the NAS's publisher: ATELIER_SCRUB_HOME=/Users/<account>)
HOME = os.environ.get("ATELIER_SCRUB_HOME") or os.path.expanduser("~")
USER = os.path.basename(HOME)


def scrub(body):
    """The home folder as ~ and the account name as `user`, in a response's text."""
    return re.sub(re.escape(USER.encode()), b"user", body.replace(HOME.encode(), b"~"), flags=re.I)
HERE = os.path.dirname(os.path.abspath(__file__))
_cache = {}  # path -> {"offset", "events", "images", "calls"}: one session file, parsed so far
_streams = {}  # key -> a stitched stream of session files (see stream())
_locks = {}
_locks_lock = threading.Lock()


def _lock(key):
    with _locks_lock:
        return _locks.setdefault(key, threading.Lock())


_models = {}  # path -> the painter's model (it doesn't change within a session)


def session_model(path):
    """The model a session ran on: the first assistant message's model, read from the top of the log once."""
    if path not in _models:
        m = ""
        try:
            with open(path, "rb") as fh:
                for _, line in zip(range(200), fh):
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    msg = d.get("message") or {}
                    if msg.get("role") == "assistant" and msg.get("model"):
                        m = msg["model"]
                        break
        except OSError:
            pass
        if not m:
            return ""  # not written yet: ask again next time
        _models[path] = m.split("/")[-1]
    return _models[path]


# painters' session folders: the export's farm (w-<work>) and the dev viewer's studios (studio-<hex>); the rest
# (work on the project, tests) the viewer doesn't list
PAINTER = re.compile(r"^(w-[a-z]+-\d{3}|studio-[0-9a-f]+)$")


def short(d):
    """A session folder's short name: w-i-001 as it is; -Users-Shared-atelier-...-studio-cfa19c -> studio-cfa19c."""
    d = d.strip("-")
    m = re.search(r"-atelier-(?:[a-z]+-)*?(studio-[0-9a-f]+)$", d)  # the atelier's studios: /Users/Shared/atelier/.../studio-<hex>
    return m.group(1) if m else d


def list_sessions():
    """One entry per painter folder (its sittings stitched: {"p": short name}); newest activity first."""
    files = {}
    for f in glob.glob(os.path.join(SESSIONS, "*", "*.jsonl")):
        files.setdefault(os.path.basename(os.path.dirname(f)), []).append(f)
    out = []
    for d, fs in files.items():
        name = short(d)
        if not PAINTER.match(name):
            continue
        fs.sort(key=os.path.basename)  # session file names begin with the start time
        info = [{"path": f, "model": session_model(f), "mtime": os.path.getmtime(f), "size": os.path.getsize(f)} for f in fs]
        models = []
        for i in info:
            if i["model"] and i["model"] not in models:
                models.append(i["model"])
        out.append({"p": name, "folder": name, "painter": True, "model": " → ".join(models), "sittings": len(fs),
                    "files": fs, "mtime": max(i["mtime"] for i in info), "size": sum(i["size"] for i in info)})
    out.sort(key=lambda s: -s["mtime"])
    return out


def painter_files(name):
    """The session files of a painter folder (given by its short name), in start order."""
    if not name or "/" in name or name.startswith("."):
        return []
    for d in glob.glob(os.path.join(SESSIONS, "*" + name + "*")):
        if short(os.path.basename(d)) == name:
            return sorted(glob.glob(os.path.join(d, "*.jsonl")), key=os.path.basename)
    return []


def _text(content):
    if isinstance(content, str):
        return content
    return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")


def parse(path):
    """Parse the log incrementally; returns (events, images)."""
    with _lock("f:" + path):
        return _parse(path)


def _parse(path):
    # changed: indices of events whose result came in after them, in arrival order (see stream())
    c = _cache.setdefault(path, {"offset": 0, "events": [], "images": [], "calls": {}, "changed": [], "cwd": ""})
    size = os.path.getsize(path)
    if size < c["offset"]:  # rewritten
        c.update(offset=0, events=[], images=[], calls={}, changed=[], cwd="")
    with open(path, "rb") as fh:
        fh.seek(c["offset"])
        chunk = fh.read()
    last_nl = chunk.rfind(b"\n")
    if last_nl < 0:
        return c["events"], c["images"]
    c["offset"] += last_nl + 1
    for line in chunk[: last_nl + 1].splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ts = d.get("timestamp", "")
        if d.get("type") in ("assistant", "user") and "sessionId" in d:  # (other lines: attachments, summaries)
            _parse_claude_code(c, d, ts)
    return c["events"], c["images"]


EASEL_TOOL = re.compile(r"^mcp__easel__(\w+)$")


def _cc_image(x):
    """(mime, base64) of a Claude Code image block, or None."""
    src = x.get("source") or {}
    if src.get("type") == "base64" and src.get("data"):
        return src.get("media_type", "image/png"), src["data"]
    if x.get("data"):  # an MCP-shaped block, if one is ever stored as it came
        return x.get("mimeType", "image/png"), x["data"]
    return None


def _parse_claude_code(c, d, ts):
    """One line of a Claude Code session transcript (<sessions>/<cwd>/<session>.jsonl) into the viewer's events:
    each assistant content block is its own line there; tool results come back in user lines. The easel's tools
    are the MCP server's (mcp__easel__paint, ...), named here without the prefix."""
    if not c["cwd"] and d.get("cwd"):
        c["cwd"] = d["cwd"]
        c["events"].append({"ts": ts, "kind": "start", "cwd": c["cwd"]})
    m = d.get("message") or {}
    content = m.get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return
    if d["type"] == "assistant":
        for x in content:
            t = x.get("type")
            if t == "text" and x.get("text", "").strip():
                c["events"].append({"ts": ts, "kind": "say", "text": x["text"]})
            elif t == "thinking" and x.get("thinking", "").strip():
                c["events"].append({"ts": ts, "kind": "think", "text": x["thinking"]})
            elif t == "tool_use":
                raw, a = x.get("name", ""), x.get("input") or {}
                g = EASEL_TOOL.match(raw)
                name = g.group(1) if g else raw
                ev = {"ts": ts, "kind": "tool", "name": name, "id": x.get("id")}
                if name == "paint":
                    ev.update(kind="paint", code=a.get("lua", ""))
                elif name == "look":
                    ev.update(kind="look", text=look_text(a))
                elif name == "note":
                    ev.update(kind="jnote", text=a.get("text", ""))
                elif name == "read":
                    ev.update(kind="read", path=a.get("path", ""))
                else:
                    ev.update(text=json.dumps(a)[:300])
                c["calls"][x.get("id")] = len(c["events"])
                c["events"].append(ev)
        return
    # user: tool results, or a message to the painter (the runner's sitting message)
    said = []
    for x in content:
        t = x.get("type")
        if t == "text":
            said.append(x.get("text", ""))
            continue
        if t != "tool_result":
            continue
        parent = c["calls"].get(x.get("tool_use_id"))
        parts = x.get("content")
        if isinstance(parts, str):
            parts = [{"type": "text", "text": parts}]
        parts = parts or []
        # Claude Code's note of where it saved an image names its config folder and the session: not the painter's
        txt = "\n".join(l for l in _text(parts).split("\n") if not l.startswith("[Image: source: "))
        if parent is not None and (txt or x.get("is_error")):
            if txt:
                c["events"][parent]["out"] = txt[-1500:]
            if x.get("is_error"):
                c["events"][parent]["err"] = True
            c["changed"].append(parent)
        for p in parts:
            if p.get("type") != "image":
                continue
            img = _cc_image(p)
            if not img:
                continue
            idx = len(c["images"])
            c["images"].append(img)
            ev = {"ts": ts, "kind": "image", "img": idx, "path": c["events"][parent].get("path", "") if parent is not None else ""}
            if parent is not None and c["events"][parent]["kind"] == "look":
                ev["look"] = c["events"][parent]["text"]
            c["events"].append(ev)
    t = "\n".join(s for s in said if s.strip())
    if t.strip() and not d.get("isMeta"):
        c["events"].append({"ts": ts, "kind": "user", "text": t[:2000]})


def look_text(args):
    """A look call's request as one line: "crop 110,540,610,900, size 800", "mode squint" ("" for the plain look)."""
    return ", ".join(f"{k} {v}" for k, v in args.items())


def is_whole(look):
    """A look request that shows the whole canvas as it is: no crop, no mode (value, squint, mirror) and not the palette."""
    return look is not None and not re.search(r"crop|mode|palette (?!False)", look)


# a closing reply that begins with the painting's title: "**The Silent Shore**", "### *Hünengrab im Abendlicht* (...)",
# also after an opening kaomoji ("(ᵔᴥᵔ) **The Old Willow at Evening**")
TITLE = re.compile(r"\s*(?:\([^)\n]{1,16}\)\S{0,3}\s+)?(?:#{1,6}\s*)?(\*\*?|__?)([^*_\n]{2,100}?)\1(?![*_\w])")
# or one on a line of its own a little further down ("I'm stopping here. ...\n\n**Quinces, Raking Light**\n\n...")
TITLE_LINE = re.compile(r"[ \t]*(?:#{1,6}[ \t]*)?(\*\*?|__?)([^*_\n]{2,100}?)\1[ \t]*")


def title_of(say):
    """The painting's title from the painter's last words; None if there is none. A label ("**Note:**") or a
    heading-like phrase ending in a colon is never a title (atelier QA Q17)."""
    t = _title_of(say)
    t = t and t.strip("\"'“”‘’ ") or None  # **"Title"**: the quotes are not the title's
    return None if t is None or t.endswith(":") or t.lower() in ("note", "notes", "why i stopped") else t


def _title_of(say):
    # the atelier's painters most often name it in their first sentence: "... and called it **Estuary, Last Light**."
    first = next((p for p in re.split(r"\n\s*\n", say or "") if p.strip()), "")
    m = re.search(r"\b(?:call(?:ed|ing)?|titled?|titling|nam(?:ed|ing|e))\s+(?:it\s+)?\*\*([^*\n]{2,80})\*\*", first)
    # ... or announce it: "The painting is finished: **"Pear Tree in Blossom"**" (i-005)
    m = m or re.search(r"\b(?:finished|complete[d]?):\s*\*\*([^*\n]{2,80})\*\*", first)
    if m:
        return m.group(1).strip()
    m = TITLE.match(say or "")
    if m:
        return m.group(2).strip()
    for para in [p for p in re.split(r"\n\s*\n", say or "") if p.strip()][1:3]:
        m = TITLE_LINE.fullmatch(para.strip("\n"))
        if m:
            return m.group(2).strip()
    return None


_warm = None  # the server's first scan of every painter for the picker: set when done (None: scan on request)
_glances = {}  # path -> what the picker needs from one session file, read incrementally without keeping images


def _glance_file(path):
    """One session file, scanned from where the last scan stopped: its image count, its newest whole look and its
    last picture (each as (index in the file, byte offset of the line, which image in the line)) and its last words.
    Images are counted as parse() counts them, so the indices match the stream's."""
    with _lock("g:" + path):
        g = _glances.get(path)
        size = os.path.getsize(path)
        if not g or size < g["offset"]:
            g = _glances[path] = {"offset": 0, "calls": {}, "n": 0, "whole": None, "last": None, "say": ""}
        with open(path, "rb") as fh:
            fh.seek(g["offset"])
            while True:
                at, line = fh.tell(), fh.readline()
                if not line.endswith(b"\n"):
                    break
                g["offset"] = fh.tell()
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") in ("assistant", "user") and "sessionId" in d:
                    _glance_claude_code(g, d, at)
        return g


def _cc_images(d):
    """The image blocks of a Claude Code user line's tool results, in order, each with its tool_use_id."""
    out = []
    for x in (d.get("message") or {}).get("content") or []:
        if isinstance(x, dict) and x.get("type") == "tool_result" and isinstance(x.get("content"), list):
            out += [(x.get("tool_use_id"), p) for p in x["content"] if p.get("type") == "image" and _cc_image(p)]
    return out


def _glance_claude_code(g, d, at):
    """_glance_file for one line of a Claude Code transcript."""
    content = (d.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    if d["type"] == "assistant":
        for x in content:
            if x.get("type") == "text" and x.get("text", "").strip():
                g["say"] = x["text"]
            elif x.get("type") == "tool_use":
                m = EASEL_TOOL.match(x.get("name", ""))
                name, a = (m.group(1) if m else x.get("name")), x.get("input") or {}
                g["calls"][x.get("id")] = look_text(a) if name == "look" else None
        return
    for k, (call, _) in enumerate(_cc_images(d)):
        g["last"] = (g["n"], at, k)
        if is_whole(g["calls"].get(call)):
            g["whole"] = g["last"]
        g["n"] += 1


def glance(files):
    """A painter's picture and title for the picker: {"look": its newest whole look (or, before the look tool, the
    last picture it saw; None if it has seen none) as a stream image index,
    "title": from its last words or None}, and where that look's bytes are, for /api/glance."""
    gs, base, look, src, last, lsrc = [_glance_file(f) for f in files], 0, None, None, None, None
    for f, g in zip(files, gs):
        if g["whole"]:
            look, src = base + g["whole"][0], (f,) + g["whole"][1:]
        if g["last"]:
            last, lsrc = base + g["last"][0], (f,) + g["last"][1:]
        base += g["n"]
    say = next((g["say"] for g in reversed(gs) if g["say"]), "")
    if look is None:
        look, src = last, lsrc
    return {"look": look, "title": title_of(say), "src": src}


def glance_image(src):
    """The bytes of the image at src (a file, a line's byte offset, which image in the line): (mime, data) or None."""
    path, at, k = src
    with open(path, "rb") as fh:
        fh.seek(at)
        d = json.loads(fh.readline())
    imgs = [_cc_image(p) for _, p in _cc_images(d)]
    return (imgs[k][0], base64.b64decode(imgs[k][1])) if k < len(imgs) else None


def _hhmm(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return ""


def stream(key, files):
    """The events of several session files (a painter's sittings) as one stream, in start
    order, with a {"kind": "sitting"} event before each sitting after the first. Image
    indices are renumbered to be unique across files. Built incrementally: each file is
    parsed from where it stopped, and only the new events are appended. If an earlier
    part changes (it shouldn't: a sitting ends before the next begins) the stream is
    rebuilt and its epoch bumped, so clients know to start over. An event already in the
    stream whose result comes in later is listed in "updates" (its stream index, in
    arrival order), so clients that have it can fetch it again."""
    with _lock("s:" + key):
        st = _streams.get(key)
        parsed = [parse(f) for f in files]
        parts = [(f, len(ev), len(im)) for f, (ev, im) in zip(files, parsed)]
        if st:
            old = st["parts"]
            same = (len(old) <= len(parts) and all(o[0] == n[0] for o, n in zip(old, parts))
                    and all(o == n for o, n in zip(old[:-1], parts))
                    and (not old or parts[len(old) - 1][1] >= old[-1][1] and parts[len(old) - 1][2] >= old[-1][2]))
            if not same:
                st = {"epoch": st["epoch"] + 1, "parts": [], "events": [], "base": [], "chg": [], "updates": []}
        else:
            st = {"epoch": 0, "parts": [], "events": [], "base": [], "chg": [], "updates": []}
        _streams[key] = st
        old, ioff = st["parts"], 0
        for k, (f, n, ni) in enumerate(parts):
            ev = parsed[k][0]
            seen = old[k][1] if k < len(old) else 0
            if seen == 0 and n and k > 0:
                st["events"].append({"ts": ev[0]["ts"], "kind": "sitting", "n": k + 1,
                                     "text": f"sitting {k + 1} · {_hhmm(ev[0]['ts'])}"})
            if k == len(st["base"]):
                st["base"].append(len(st["events"]))  # where this file's events begin in the stream
            if k == len(st["chg"]):
                st["chg"].append(0)
            changed = _cache[f]["changed"]
            for j in changed[st["chg"][k]:]:
                if j < seen:  # already sent without its result
                    st["updates"].append(st["base"][k] + j)
            st["chg"][k] = len(changed)
            for e in ev[seen:n]:
                st["events"].append(dict(e, img=e["img"] + ioff) if e["kind"] == "image" else e)
            ioff += ni
        st["parts"] = parts
        return st


def painting_sources(events):
    """The folder to read the painting's source from (the painter's: its last start) and the files, relative to it,
    the page may ask for: paintings/lua/painting.lua only. Nothing else in the folder (the brief, notes, bin/,
    settings) is served."""
    cwd = next((e["cwd"] for e in reversed(events) if e["kind"] == "start"), "")
    return cwd, {"paintings/lua/painting.lua"}


def image(st, i):
    """Image i of a stitched stream: (mime, base64 data), or None."""
    for f, _, ni in st["parts"]:
        if i < ni:
            imgs = _cache[f]["images"]
            return imgs[i] if 0 <= i < len(imgs) else None
        i -= ni
    return None


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        if PUBLIC and not ctype.startswith("image/"):
            body = scrub(body)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # a look never changes: the browser keeps it (and asks again for everything else)
        self.send_header("Cache-Control", "private, max-age=86400, immutable" if ctype.startswith("image/") else "no-store")
        if PUBLIC:
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        # what to show: ?p=<painter folder> (all its sittings)
        painter = q.get("p", [""])[0]
        if painter and not PAINTER.match(painter):
            return self._send(404, b"not found", "text/plain")
        if u.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if u.path == "/api/sessions":
            ss = list_sessions()
            for s in ss:
                # the picker's picture and title (the static export has them in sessions.json); until the first scan is done, without
                if _warm is None or _warm.is_set():
                    g = glance(s["files"])
                    s.update(look=g["look"], title=g["title"])
            if PUBLIC:
                ss = [{k: v for k, v in s.items() if k != "files"} for s in ss]
            return self._send(200, json.dumps(ss).encode(), "application/json")
        if u.path == "/api/glance":  # a painter's picture in the picker, read alone (not the painter's whole log)
            files = painter_files(painter)
            g = glance(files) if files else None
            im = glance_image(g["src"]) if g and g["src"] else None
            return self._send(200, im[1], im[0]) if im else self._send(404, b"not found", "text/plain")
        if u.path not in ("/api/events", "/api/file", "/img"):
            return self._send(404, b"not found", "text/plain")
        files = painter_files(painter)
        if not files:
            return self._send(404, b"no such session", "text/plain")
        st = stream("p:" + painter, files)
        if u.path == "/api/events":
            since, ev = int(q.get("since", ["0"])[0]), st["events"]
            if q.get("epoch", [str(st["epoch"])])[0] != str(st["epoch"]):
                since = 0  # the stream was rebuilt: the client starts over
            # u: how many updates the client has seen; it gets the rest as [index, event], for indices < since
            u = int(q.get("u", ["0"])[0]) if q.get("epoch", [""])[0] == str(st["epoch"]) else 0
            ups = [[i, ev[i]] for i in st["updates"][u:] if i < since]
            return self._send(200, json.dumps({"events": ev[since:], "total": len(ev), "epoch": st["epoch"],
                                               "sittings": len(files), "updates": ups,
                                               "nupdates": len(st["updates"])}).encode(), "application/json")
        if u.path == "/api/file":  # the painting's current source, from the painter's folder
            cwd, rels = painting_sources(st["events"])
            rel = q.get("f", [""])[0]
            want = os.path.realpath(os.path.join(cwd, rel))
            if cwd and rel in rels and want.startswith(os.path.realpath(cwd) + os.sep) and os.path.isfile(want):
                with open(want, "rb") as fh:
                    return self._send(200, fh.read(), "text/plain; charset=utf-8")
            return self._send(404, b"", "text/plain")
        if u.path == "/img":
            im = image(st, int(q.get("i", ["0"])[0]))
            if im:
                return self._send(200, base64.b64decode(im[1]), im[0])
        self._send(404, b"not found", "text/plain")


def main():
    global SESSIONS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="e.g. this machine's Tailscale IP to watch from another of your devices")
    ap.add_argument("--sessions", default=SESSIONS, help="the painters' Claude Code transcripts, a folder per painter")
    ap.add_argument("--public", action="store_true", help="painters only, home path and account name scrubbed (a link for others)")
    a = ap.parse_args()
    SESSIONS = os.path.abspath(os.path.expanduser(a.sessions))
    global PUBLIC
    PUBLIC = a.public
    global _warm
    _warm = threading.Event()

    def warm():  # the picker's pictures and titles, read ahead (the first scan reads every log once: seconds)
        import time
        while True:
            for s in list_sessions():
                glance(s["files"])
            _warm.set()
            time.sleep(30)
    threading.Thread(target=warm, daemon=True).start()
    print(f"studio: http://{a.host}:{a.port}" + (" (public: painters only, scrubbed)" if PUBLIC else ""))
    # a thumbnail strip asks for dozens of images at once: the default queue of 5 connections
    # reset the rest ("Connection reset by peer")
    class Server(http.server.ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True
    Server((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
