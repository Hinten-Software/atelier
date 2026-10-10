#!/usr/bin/env python3
"""The NAS's publisher (docs/design-nas-publisher.md; requirements OPS-2, OPS-4, REC-3): the Mac paints, the NAS
does the rest. Reads the Mac's store and the artists' roots from read-only shares; exports the site, copies it into
the folder nginx serves, and backs the store and the roots up into the archive.

    python3 runner/publish.py            every ATELIER_EVERY seconds, for as long as it runs (the container)
    python3 runner/publish.py --once     one round: export if anything changed, back up if a sitting ended

The export runs when anything it reads has changed (every 2 minutes at most while a work paints). The backup runs
when a work's state changes (a sitting ends, a work hangs) and once a night at ATELIER_BACKUP_AT. Nothing is ever
written into the store. What happened last is in ATELIER_STATUS (JSON), never the private text of a blocked export.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, REPO, WORK  # noqa: E402
from export import hidden  # noqa: E402

SITE_OUT = Path(os.environ.get("ATELIER_SITE_OUT", "/site"))      # the shared folder nginx serves (atelier-site)
BACKUP_OUT = Path(os.environ.get("ATELIER_BACKUP_OUT", "/backup"))  # the archive (atelier-backup)
STATUS = Path(os.environ.get("ATELIER_STATUS", BACKUP_OUT / "status" / "status.json"))
EVERY = int(os.environ.get("ATELIER_EVERY", "120"))  # seconds (OPS-4)
BACKUP_AT = os.environ.get("ATELIER_BACKUP_AT", "07:15")  # the nightly backup, after the painting window
RSYNC = os.environ.get("ATELIER_RSYNC", "rsync")

# never copied into the archive: secrets (until they leave the store), the pinned harness (re-downloadable), the
# Mac's old export folders
BACKUP_EXCLUDES = ["/secrets/", "/bin/", "/run/stage/", "/run/farm/", "/site/", "/site.new/", "/site.old/",
                   "/run/*/check/"]
# in an artist's root: Claude Code's own caches; the transcripts under .config/projects stay
ROOT_EXCLUDES = [".config/backups/", ".config/policy-limits*", ".config/remote-settings.json", "Library/", "studio/bin/",
                 "studio/out/easel/*.sock"]
# DSM's own folders in every share (recycle bin, thumbnails): never touched, never deleted
SYNOLOGY_OWN = ["--exclude=#recycle", "--exclude=@eaDir", "--exclude=#snapshot"]


def say(msg: str):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def stamp(p: Path):
    try:
        st = p.stat()
        return (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(p), None, None)


def states() -> list[Path]:
    return sorted((DATA / "run").glob("*/state.json"))


def export_inputs() -> tuple:
    """Everything the export reads, as (path, mtime, size): unchanged means the site would come out the same."""
    files = [DATA / "artists.json", DATA / "notes.json"]
    files += sorted((DATA / "artists").glob("*/birth.json")) + sorted((DATA / "artists").glob("*/walls-at-birth/*.png"))
    for w in sorted((DATA / "works").glob("*-[0-9][0-9][0-9]")):
        files += sorted(f for f in w.iterdir() if f.is_file()) + sorted((w / "sessions").glob("*.jsonl"))
    for sf in states():
        files.append(sf)
        try:
            files += [Path(r["transcript"]) for r in json.loads(sf.read_text()).get("sittings", [])]
        except (OSError, ValueError, KeyError):
            pass  # a state being written: its new stamp brings the next round
    files += sorted(f for f in (REPO / "site").rglob("*") if f.is_file() and not hidden(f.relative_to(REPO / "site")))
    return tuple(stamp(f) for f in files)


def backup_inputs() -> tuple:
    """A sitting ending or a work hanging changes its state or manifest."""
    return tuple(stamp(f) for f in states() + sorted((DATA / "works").glob("*/manifest.json")))


def rsync(args: list[str], what: str) -> tuple[bool, str]:
    r = subprocess.run([RSYNC, "-rlt", *SYNOLOGY_OWN, *args], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        msg = f"{what} failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-400:]}"
        say(msg)
        return False, msg
    say(f"{what}: ok")
    return True, ""


def export() -> tuple[bool, str]:
    """The export into WORK/site, then into the served folder as one consistent state: new files land at the end,
    together; stale ones go after. A blocked export leaves the served site as it was."""
    r = subprocess.run([sys.executable, str(REPO / "runner" / "export.py")], capture_output=True, text=True,
                       env=os.environ | {"ATELIER_DATA": str(DATA), "ATELIER_WORK": str(WORK)})
    if r.returncode:
        blocked = WORK / "run" / "export-blocked.txt"  # redacted by the export: what and where, never the text
        why = blocked.read_text().strip() if r.returncode == 2 and blocked.exists() else (r.stderr or r.stdout).strip()[-400:]
        say(f"export failed ({r.returncode}): {why}")
        return False, why
    SITE_OUT.mkdir(parents=True, exist_ok=True)
    return rsync(["--chmod=D755,F644", "--delete-delay", "--delay-updates", f"{WORK / 'site'}/", f"{SITE_OUT}/"], "site copy")


def backup() -> tuple[bool, str]:
    """The store and every artist's root (studio, notebook, transcripts), mirrored; the NAS's snapshots keep history."""
    (BACKUP_OUT / "data").mkdir(parents=True, exist_ok=True)
    ok, why = rsync(["--delete", *[f"--exclude={e}" for e in BACKUP_EXCLUDES], f"{DATA}/", f"{BACKUP_OUT / 'data'}/"],
                    "backup data")
    reg = DATA / "artists.json"
    for a, rec in sorted((json.loads(reg.read_text()) if reg.exists() else {}).items()):
        root = Path(rec["root"])  # mounted at its path on the Mac, so the transcripts' paths hold
        if not root.exists():
            ok, why = False, f"backup root {a}: {root} is not mounted"
            say(why)
            continue
        (BACKUP_OUT / f"root-{a}").mkdir(exist_ok=True)
        r_ok, r_why = rsync(["--delete", *[f"--exclude={e}" for e in ROOT_EXCLUDES], f"{root}/", f"{BACKUP_OUT / f'root-{a}'}/"],
                            f"backup root {a}")
        ok, why = ok and r_ok, why or r_why
    return ok, why


def load_status() -> dict:
    try:
        return json.loads(STATUS.read_text())
    except (OSError, ValueError):
        return {}


def save_status(st: dict):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(STATUS)


def store_reachable() -> bool:
    """The Mac's share is mounted and answers (a Mac that is away delays the site; nothing is lost)."""
    return (DATA / "artists.json").exists()


class Publisher:
    def __init__(self):
        self.status = load_status()
        self.seen_export = None  # first round always exports: the code or the pages may have changed
        # a restart does not back up again what was already backed up (the stamps are kept in the status)
        self.seen_backup = tuple(tuple(s) for s in self.status.get("backup_inputs") or ()) or None

    def round(self, now: datetime | None = None):
        now = now or datetime.now()
        when = now.isoformat(timespec="seconds")
        if not store_reachable():
            if self.status.get("store") != "away":
                say(f"the store is not reachable at {DATA}; waiting")
            self.status["store"] = "away"
            save_status(self.status)
            return
        self.status["store"] = "ok"
        inputs = export_inputs()
        if inputs != self.seen_export:
            ok, why = export()
            self.status["export"] = {"at": when, "ok": ok, "why": why}
            if ok:
                self.seen_export = inputs
        b_inputs = backup_inputs()
        nightly = now.strftime("%H:%M") >= BACKUP_AT and self.status.get("nightly") != now.date().isoformat()
        if b_inputs != self.seen_backup or nightly:
            ok, why = backup()
            self.status["backup"] = {"at": when, "ok": ok, "why": why}
            if ok:
                self.seen_backup = b_inputs
                self.status["backup_inputs"] = [list(s) for s in b_inputs]
                if nightly:
                    self.status["nightly"] = now.date().isoformat()
        save_status(self.status)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    p = Publisher()
    if a.once:
        p.round()
        st = p.status
        return 0 if all(st.get(k, {}).get("ok", True) for k in ("export", "backup")) and st.get("store") == "ok" else 1
    say(f"publisher: {DATA} -> {SITE_OUT}, {BACKUP_OUT}; every {EVERY} s, nightly backup at {BACKUP_AT}")
    while True:
        try:
            p.round()
        except Exception as e:  # noqa: BLE001  (one bad round never ends the publisher)
            say(f"round error: {e!r}")
        time.sleep(EVERY)


if __name__ == "__main__":
    sys.exit(main())
