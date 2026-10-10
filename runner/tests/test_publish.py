#!/usr/bin/env python3
"""The NAS's publisher (docs/design-nas-publisher.md): it exports from a read-only store into a folder of its own,
copies the site into the served folder, backs up the store and the roots, writes nothing into the store, skips a
round when nothing changed, and leaves the served site as it was when an export is blocked. The painter's home
path is scrubbed even though the export runs on another machine (ATELIER_SCRUB_HOME).

    python3 runner/tests/test_publish.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_export as T  # noqa: E402  (its fake works and transcripts)

BASE = Path(f"/Users/Shared/atelier/p{os.getpid() % 10000}")
DATA, WORK, SITE, BACKUP, ROOT = BASE / "data", BASE / "work", BASE / "site", BASE / "backup", BASE / "root-i"
T.DATA = DATA
ENV = os.environ | {"ATELIER_DATA": str(DATA), "ATELIER_WORK": str(WORK), "ATELIER_SITE_OUT": str(SITE),
                    "ATELIER_BACKUP_OUT": str(BACKUP), "ATELIER_RSYNC": "/opt/homebrew/bin/rsync",
                    "ATELIER_SCRUB_HOME": "/Users/gh0st", "ATELIER_BACKUP_AT": "99:99"}  # no nightly round in tests


def publish():
    r = subprocess.run(["/opt/homebrew/bin/uv", "run", "-q", "--with", "pillow", "python3", str(HERE.parent / "publish.py"),
                        "--once"], env=ENV, capture_output=True, text=True)
    return r, json.loads((BACKUP / "status" / "status.json").read_text())


def tree(p: Path) -> dict:
    return {str(f.relative_to(p)): f.stat().st_mtime_ns for f in p.rglob("*")}


def readonly(on: bool):
    for f in [DATA, *DATA.rglob("*")]:
        if not f.is_symlink():
            f.chmod((f.stat().st_mode & ~0o222) if on else (f.stat().st_mode | 0o200))


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    try:
        T.work("i-001", extra=" Like /Users/gh0st/Desktop, and gh0st's things.")
        ROOT.mkdir(parents=True)
        (ROOT / "notebook").write_text("pears\n")
        (DATA / "artists.json").write_text(json.dumps({"i": {"root": str(ROOT), "studio_name": "Studio I"}}))
        readonly(True)
        before = tree(DATA)

        r, st = publish()
        T.check("a round exports, copies and backs up", r.returncode == 0 and st["export"]["ok"] and st["backup"]["ok"],
                r.stdout[-400:] + r.stderr[-400:])
        T.check("the served folder has the work", (SITE / "studio/data/w-i-001/events.json").exists())
        T.check("the export was built outside the store", (WORK / "site/data/works.json").exists())
        T.check("nothing written into the store", tree(DATA) == before)
        ev = (SITE / "studio/data/w-i-001/events.json").read_text()
        T.check("the painter's home and account scrubbed", "gh0st" not in ev and "/Users/" not in ev, ev[:300])
        T.check("the store backed up", (BACKUP / "data/works/i-001/manifest.json").exists())
        T.check("the root backed up", (BACKUP / "root-i/notebook").read_text() == "pears\n")

        r, st2 = publish()  # a fresh process: as after a restart
        T.check("a restart does not back up again", st2["backup"]["at"] == st["backup"]["at"], st2.get("backup"))

        served = (SITE / "studio/data/w-i-001/events.json").read_text()
        readonly(False)
        T.work("i-002", extra=" Write to someone@example.com.")
        readonly(True)
        r, st = publish()
        T.check("a leak blocks the round", r.returncode == 1 and not st["export"]["ok"], st.get("export"))
        T.check("the status names the problem, not the text", "email" in st["export"]["why"]
                and "example.com" not in json.dumps(st), st["export"])
        T.check("the served site is as it was", not (SITE / "studio/data/w-i-002").exists()
                and (SITE / "studio/data/w-i-001/events.json").read_text() == served)
        T.check("a changed state is backed up", (BACKUP / "data/works/i-002/manifest.json").exists())

        readonly(False)
        shutil.move(DATA / "artists.json", BASE / "away.json")  # the Mac's share gone
        r, st = publish()
        T.check("a store that is away is waited for", r.returncode == 1 and st["store"] == "away", st)
    finally:
        if DATA.exists():
            readonly(False)
        shutil.rmtree(BASE, ignore_errors=True)
    print("all passed" if not T.failed else f"{T.failed} failed")
    sys.exit(1 if T.failed else 0)


if __name__ == "__main__":
    main()
