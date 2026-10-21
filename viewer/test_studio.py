"""The viewer's server and static export, on synthetic Claude Code transcripts in a temp folder.

    uv run --with pytest --with pillow pytest viewer/test_studio.py
"""
import http.server
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import studio as S

PAINTER = "w-i-001"  # a work's folder in the export's session farm


def line(role, content, **kw):
    """One line of a Claude Code transcript."""
    return json.dumps(dict({"type": role, "sessionId": "s1", "timestamp": "2026-09-29T10:00:00.000Z",
                            "message": {"role": role, "content": content}}, **kw)) + "\n"


def start(cwd):
    return line("user", "Your brief is in BRIEF.md in this folder.", cwd=cwd)


def use(i, tool, args):
    return {"type": "tool_use", "id": i, "name": "mcp__easel__" + tool, "input": args}


def call(i, lua):
    return line("assistant", [use(i, "paint", {"lua": lua})])


def result(i, text):
    return line("user", [{"type": "tool_result", "tool_use_id": i, "content": [{"type": "text", "text": text}]}])


def picture(i, png):
    import base64
    return line("user", [{"type": "tool_result", "tool_use_id": i, "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}}]}])


@pytest.fixture
def home(tmp_path):
    """A home with a painter's studio folder (brief, notes, easel, the painting) and its session folder."""
    studio = tmp_path / "studio"
    for rel, body in {"BRIEF.md": "the brief", "notes/materials.md": "notes", "bin/easel": "binary",
                      "paintings/lua/painting.lua": "canvas{}"}.items():
        (studio / rel).parent.mkdir(parents=True, exist_ok=True)
        (studio / rel).write_text(body)
    sessions = tmp_path / "farm" / PAINTER
    sessions.mkdir(parents=True)
    return tmp_path, studio, sessions / "s1.jsonl"


@pytest.fixture
def server(home, monkeypatch):
    monkeypatch.setattr(S, "SESSIONS", str(home[0] / "farm"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    fetch = lambda q: get(fetch.base + q)
    fetch.base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield fetch
    srv.shutdown()
    srv.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def test_file_endpoint_serves_the_painting_source_only(home, server):
    _, studio, log = home
    log.write_text(start(str(studio)) + call("c1", "canvas{}") + result("c1", "ok · chunk 1"))
    assert server(f"/api/file?p={PAINTER}&f=paintings/lua/painting.lua") == (200, b"canvas{}")
    for f in ("BRIEF.md", "notes/materials.md", "bin/easel"):
        assert server(f"/api/file?p={PAINTER}&f={f}")[0] == 404, f


def test_a_late_result_reaches_a_client_that_already_had_the_call(home, server):
    _, studio, log = home
    log.write_text(start(str(studio)) + call("c1", "canvas{}"))
    r = json.loads(server(f"/api/events?p={PAINTER}&since=0")[1])
    i = next(k for k, e in enumerate(r["events"]) if e["kind"] == "paint")
    assert "out" not in r["events"][i]
    with open(log, "a") as fh:
        fh.write(result("c1", "ok · chunk 1"))
    r2 = json.loads(server(f"/api/events?p={PAINTER}&since={r['total']}&epoch={r['epoch']}&u={r['nupdates']}")[1])
    assert [(k, e["out"]) for k, e in r2["updates"]] == [(i, "ok · chunk 1")]
    # and only once
    r3 = json.loads(server(f"/api/events?p={PAINTER}&since={r2['total']}&epoch={r2['epoch']}&u={r2['nupdates']}")[1])
    assert r3["updates"] == []


def export(tmp_path, out):
    env = dict(os.environ, HOME=str(tmp_path))
    return subprocess.run([sys.executable, os.path.join(HERE, "export_static.py"), str(out), "--sessions", str(tmp_path / "farm")],
                          env=env, capture_output=True, text=True)


def test_export_refuses_a_folder_it_does_not_own(home):
    tmp_path, studio, log = home
    log.write_text(start(str(studio)) + call("c1", "canvas{}") + result("c1", "ok · chunk 1"))
    out = tmp_path / "out"
    out.mkdir()
    before = sorted(str(p.relative_to(out)) for p in out.rglob("*"))
    (out / "keep.txt").write_text("not the exporter's")
    r = export(tmp_path, out)
    assert r.returncode != 0 and ".studio-export" in r.stderr
    assert sorted(str(p.relative_to(out)) for p in out.rglob("*")) == sorted(before + ["keep.txt"])


def test_export_prunes_only_files_it_wrote(home):
    tmp_path, studio, log = home
    log.write_text(start(str(studio)) + call("c1", "canvas{}") + result("c1", "ok · chunk 1"))
    out = tmp_path / "out"
    assert export(tmp_path, out).returncode == 0
    source = out / "data" / PAINTER / "file" / "paintings" / "lua" / "painting.lua"
    assert source.read_text() == "canvas{}"
    (out / "data" / "mine.txt").write_text("added by hand")
    (studio / "paintings" / "lua" / "painting.lua").unlink()
    r = export(tmp_path, out)
    assert r.returncode == 0, r.stderr
    assert not source.exists()  # the export's own file, stale now
    assert (out / "data" / "mine.txt").read_text() == "added by hand"


def look(i, png):
    """A look and the picture it returned."""
    return line("assistant", [use(i, "look", {})]) + picture(i, png)


def test_export_makes_small_web_copies_of_each_look_and_remakes_them_when_it_changes(home):
    Image = pytest.importorskip("PIL.Image")
    import io

    def png(w, h, color):
        buf = io.BytesIO()
        Image.new("RGB", (w, h), color).save(buf, "PNG")
        return buf.getvalue()

    tmp_path, studio, log = home
    log.write_text(start(str(studio)) + look("l1", png(2400, 1600, (200, 30, 30))))
    out = tmp_path / "out"
    assert export(tmp_path, out).returncode == 0
    d = out / "data" / PAINTER
    assert json.loads((d / "events.json").read_text())["web"] == [1]
    assert Image.open(d / "img" / "0.png").size == (2400, 1600)  # the original, for the zoom
    assert max(Image.open(d / "v" / "0.jpg").size) == 1600
    assert max(Image.open(d / "t" / "0.jpg").size) <= 168

    # the session is rewritten with a different picture at the same index: its copies follow it
    log.write_text(start(str(studio)) + look("l1", png(1200, 800, (30, 30, 200))))
    assert export(tmp_path, out).returncode == 0
    assert Image.open(d / "v" / "0.jpg").convert("RGB").getpixel((5, 5))[2] > 150


def png_of(color):
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, "PNG")
    return buf.getvalue()


def looks_at_once(*calls):
    """Several looks in one message ((id, arguments, png) each), their pictures coming back one result at a time."""
    out = "".join(line("assistant", [use(i, "look", a)]) for i, a, _ in calls)
    for i, _, png in calls:
        out += picture(i, png)
    return out


def say(text):
    return line("assistant", [{"type": "text", "text": text}])


@pytest.mark.parametrize("via", ["live server", "static export"])
def test_the_picker_gets_the_newest_whole_look_and_the_title_from_the_closing_reply(home, server, via):
    # a whole look, then a whole look and a squint asked for together: the picture is the second whole look,
    # not the squint whose result came last; the title is the one the closing reply begins with
    pytest.importorskip("PIL")
    tmp_path, studio, log = home
    log.write_text(start(str(studio)) + look("l1", png_of("red"))
                   + looks_at_once(("l2", {"size": 800}, png_of("blue")), ("l3", {"mode": "squint"}, png_of("green")))
                   + say("**The Blue Barn**\n\nA barn at dusk."))
    if via == "live server":
        p = next(s for s in json.loads(server("/api/sessions")[1]) if s.get("p") == PAINTER)
        code, picture = server(f"/api/glance?p={PAINTER}&i={p['look']}")
        assert code == 200
    else:
        out = tmp_path / "out"
        r = export(tmp_path, out)
        assert r.returncode == 0, r.stderr
        p = next(s for s in json.loads((out / "data" / "sessions.json").read_text()) if s["p"] == PAINTER)
        picture = (out / "data" / PAINTER / "img" / f"{p['look']}.png").read_bytes()
    assert (p["look"], p["title"]) == (1, "The Blue Barn")
    assert picture == png_of("blue")


@pytest.mark.parametrize("say, title", [
    ("**The Blue Barn**\n\nA barn at dusk.", "The Blue Barn"),
    # a sign-off line first, the title alone on the next paragraph
    ("I'm stopping here. The painting is finished as far as I can take it.\n\n**Quinces, Raking Light**\n\nA low-key still life.", "Quinces, Raking Light"),
    # announced with a colon, in quotes inside the bold (atelier i-005)
    ('The painting is finished: **"Pear Tree in Blossom"**\n\nIt\'s a spring morning.', "Pear Tree in Blossom"),
    ("I'm done for today: **more glazes** tomorrow, I think.", None),
    ("I'll start by reading the brief.", None),
    ("Next I'll **glaze** the sky.\n\nThen the trees.", None),
])
def test_the_title_is_where_painters_put_it_in_their_closing_words(say, title):
    assert S.title_of(say) == title


def test_a_palette_look_is_not_the_painting():
    # the easel's palette look (look{palette=true}) shows the mixed piles, not the canvas
    assert S.is_whole(S.look_text({}))
    assert S.is_whole(S.look_text({"size": 800}))
    assert not S.is_whole(S.look_text({"palette": True}))
    assert S.is_whole(S.look_text({"palette": False}))


@pytest.mark.parametrize("ending, said", [
    (say("End of this sitting: the sky is laid in."), True),  # between sittings (or done): the website lists it a while
    (call("p1", "x = 1"), False),  # cut off mid-step
])
def test_the_export_says_whether_a_run_stopped_on_its_own_words(home, ending, said):
    tmp_path, studio, log = home
    log.write_text(start(str(studio)) + say("I'll start by reading the brief.") + ending)
    out = tmp_path / "out"
    r = export(tmp_path, out)
    assert r.returncode == 0, r.stderr
    p = next(s for s in json.loads((out / "data" / "sessions.json").read_text()) if s["p"] == PAINTER)
    assert p["said"] is said
