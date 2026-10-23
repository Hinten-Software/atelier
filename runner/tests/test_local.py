#!/usr/bin/env python3
"""A painter on a local model (the owner, 2026-10-22): their environment, their sittings' threshold and cost, the
audit's form of Claude Code's model notice for them, their birth only in a store not pushed to the NAS, an export of
a pushed store without them, and a work that waits while LM Studio isn't there. A stand-in LM Studio answers here.

    python3 runner/tests/test_local.py
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(f"/Users/Shared/atelier/t{os.getpid() % 10000}")
os.environ |= {"ATELIER_DATA": str(DATA), "ATELIER_SECRETS": str(DATA / "secrets"), "ATELIER_WINDOW": "always",
               "ATELIER_CLAUDE": str(HERE / "fake_claude.py"), "ATELIER_WAIT_SCALE": "0.002"}
sys.path.insert(0, str(HERE.parent))
import audit  # noqa: E402
import budget  # noqa: E402
from config import LOCAL_MIN_CONTEXT, artist_env, local_context_limit, local_ready  # noqa: E402

failed = 0
MODEL = "google/gemma-4-e4b"
LOADED = {"context": 65105}


def check(what, cond, detail=""):
    global failed
    failed += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{'' if cond else ': ' + str(detail)}")


class LMStudio(BaseHTTPRequestHandler):
    """LM Studio's own model API, as far as local_ready asks it."""
    def do_GET(self):
        if self.path != f"/api/v0/models/{MODEL.replace('/', '%2F')}" and self.path != f"/api/v0/models/{MODEL}":
            self.send_response(400)
            self.end_headers()
            return
        body = json.dumps({"id": MODEL, "type": LOADED.get("type", "vlm"), "state": "loaded",
                           "loaded_context_length": LOADED["context"]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def atelier(*args, env=None):
    r = subprocess.run([sys.executable, str(HERE.parent / "atelier.py"), *args], env=os.environ | (env or {}),
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    DATA.mkdir(parents=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), LMStudio)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    local = {"url": url, "model": MODEL}
    roots = []
    try:
        # the environment: every request to the local server, nothing of the owner's login
        (DATA / "secrets").mkdir()
        os.environ["ATELIER_SECRETS"] = str(DATA / "secrets")
        root = Path("/Users/Shared/xx-test")
        env = artist_env(Path("/tmp/cfg"), root, local)
        check("a local sitting's requests go to LM Studio", env["ANTHROPIC_BASE_URL"] == url, env)
        check("... its background requests too", env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == MODEL == env["ANTHROPIC_SMALL_FAST_MODEL"])
        check("... with no OAuth token and no keychain login", "CLAUDE_CODE_OAUTH_TOKEN" not in env and "USER" not in env, env)
        check("... and nothing else to Anthropic", env.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC") == "1")
        check("... HOME is the painter's root", env["HOME"] == str(root), env["HOME"])
        check("a Claude painter's environment has no local server", "ANTHROPIC_BASE_URL" not in artist_env(Path("/tmp/cfg"), root))

        # LM Studio's readiness and the sitting's threshold
        check("the loaded context is read from LM Studio", local_ready(local) == 65105, local_ready(local))
        LOADED["context"] = 8192
        check("a context too small for a sitting is refused", isinstance(local_ready(local), str) and "49152" in local_ready(local))
        LOADED["context"] = 65105
        LOADED["type"] = "llm"
        check("a model that can't see pictures is refused", "can't see pictures" in str(local_ready(local)), local_ready(local))
        LOADED["type"] = "vlm"
        check("an unknown model is refused", "no model" in str(local_ready({"url": url, "model": "nope/x"})))
        check("a server that isn't on is refused", "isn't answering" in str(local_ready({"url": "http://127.0.0.1:9", "model": MODEL})))
        lim = local_context_limit(65105)
        check("the threshold leaves room for a tool result and a reply", 30_000 < lim < 65105 - 20_000, lim)
        check("... and is never below half the context", local_context_limit(LOCAL_MIN_CONTEXT) >= LOCAL_MIN_CONTEXT // 2)

        # cost: nothing for a local model; an unknown model on Claude still priced high
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        m = budget.Meter(free=True)
        m.add({"type": "assistant", "message": {"id": "a", "model": MODEL, "usage": usage}})
        check("a local sitting costs nothing", m.usd == 0, m.usd)
        m = budget.Meter()
        m.add({"type": "assistant", "message": {"id": "a", "model": MODEL, "usage": usage}})
        check("... but an unknown model on a Claude painter is still priced high", m.usd == 10.0, m.usd)

        # the audit: Claude Code's notice of a local model, and nothing more in its place
        def model_att(text):
            return audit.check_line({"type": "attachment", "attachment": {"type": "model"},
                                     "rendered": [{"content": text}]}, set(), Path("/tmp/cfg"))
        check("the audit accepts the local model notice",
              model_att(f"<system-reminder>\nYou are powered by the model {MODEL}.\n</system-reminder>") == [])
        check("... and nothing added to it", model_att(f"<system-reminder>\nYou are powered by the model {MODEL}. Hi\n</system-reminder>") != [])
        check("... the Claude notice still passes", model_att("<system-reminder>\nYou are powered by the model named Opus 5.5. "
              "The exact model ID is claude-opus-5-5. Assistant knowledge cutoff is June 2026.\n</system-reminder>") == [])

        nudge = {"type": "user", "message": {"content": next(iter(audit.LOCAL_NUDGES))}}
        check("Claude Code's empty-reply nudge passes for a local painter",
              audit.check_line(nudge, audit.LOCAL_NUDGES, Path("/tmp/cfg")) == [])
        check("... and is still a hit for a Claude painter", audit.check_line(nudge, set(), Path("/tmp/cfg")) != [])

        # birth: refused in a store pushed to the NAS; in a private one, the birth record says where the model is
        (DATA / "nas.json").write_text('{"host": "nas.test"}')
        rc, out = atelier("birth", "--without-probes", "--local", MODEL, "--local-url", url, "--studio", "iv")
        check("no local painter is born in a store pushed to the NAS", rc and "private store" in out, out)
        (DATA / "nas.json").unlink()
        rc, out = atelier("birth", "--local", MODEL, "--local-url", url, "--studio", "iv")
        check("a local birth needs the local probes", rc and "--local" in out, out)
        rc, out = atelier("birth", "--without-probes", "--local", MODEL, "--local-url", "http://127.0.0.1:9", "--studio", "iv")
        check("... and LM Studio answering", rc and "isn't answering" in out, out)
        rc, out = atelier("birth", "--without-probes", "--local", MODEL, "--local-url", url, "--studio", "iv")
        check("a local painter is born in a private store", rc == 0, out)
        reg = json.loads((DATA / "artists.json").read_text())
        roots.append(Path(reg["iv"]["root"]))
        rec = json.loads((DATA / "artists" / "iv" / "birth.json").read_text())
        check("... their birth record names the model and the server", rec["model"] == MODEL and rec["local"] == local, rec)

        # an export of a store pushed to the NAS leaves them out, works and birth record
        sys.path.insert(0, str(HERE.parent))
        import export
        (DATA / "works" / "iv-001").mkdir(parents=True)
        (DATA / "works" / "iv-001" / "manifest.json").write_text(json.dumps({"id": "iv-001", "finished": True}))
        works = export.farm()
        check("a private store's export has them", any(w.name == "iv-001" for w in works), works)
        (DATA / "nas.json").write_text('{"host": "nas.test"}')
        check("a pushed store's export leaves their works out", not any(w.name == "iv-001" for w in export.farm()))
        check("... and their birth record", all(a["id"] != "iv" for a in export.works_json([])["artists"]))
        (DATA / "nas.json").unlink()
        shutil.rmtree(DATA / "works" / "iv-001")

        # a work while LM Studio isn't there: no sitting, and a wait as for a usage limit; nothing in "sittings"
        rec["local"]["url"] = "http://127.0.0.1:9"
        (DATA / "artists" / "iv" / "birth.json").write_text(json.dumps(rec))
        (DATA / "bin").mkdir(exist_ok=True)
        rc, out = atelier("paint", "iv", "--by", "owner")
        check("a work starts", rc == 0, out)
        work = "iv-001"
        st = {}
        for _ in range(240):
            st = json.loads((DATA / "run" / work / "state.json").read_text())
            if st.get("not_ready") and st["state"] == "limit-wait":
                break
            time.sleep(0.5)
        subprocess.run(["pkill", "-f", f"atelier.py run {work}"])
        check("without LM Studio the work waits for it", st["state"] == "limit-wait" and st.get("waiting_for") == "the local model", st)
        check("... with no sitting recorded", st["sittings"] == [], st["sittings"])
        check("... and the reason kept", "isn't answering" in (st.get("not_ready") or ""), st.get("not_ready"))
        check("... not counted as a crash", st["crashes"] == 0, st["crashes"])
    finally:
        server.shutdown()
        for r in roots:
            shutil.rmtree(r, ignore_errors=True)
        shutil.rmtree(DATA, ignore_errors=True)
    print("all ok" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
