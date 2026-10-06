"""The atelier's plumbing to the NAS (requirements OPS-2, OPS-9): the live site and the backups.

    atelier sync        the published site to the NAS's `atelier-site` folder
    atelier backup      the atelier's records to the NAS's `atelier-backup` folder

Both go through DSM's rsync service as a user that can write those two folders and nothing else
(deploy/nas/README.md). The NAS's address and that user live in DATA/nas.json, its password in
DATA/secrets/nas-sync-password (tools/save-token.sh nas): nothing of either is in the repository.
Without them both are quietly skipped, so the atelier runs the same with or without a NAS.

The NAS keeps daily snapshots of both folders: the Mac can overwrite them, only the NAS can delete history.
"""
import json
import subprocess
import time
from pathlib import Path

from config import DATA

RSYNC = "/opt/homebrew/bin/rsync"  # openrsync (macOS) has no daemon password file
SETTINGS = DATA / "nas.json"        # {"host": "...", "user": "atelier-sync", "site": "atelier-site", "backup": "atelier-backup"}
PASSWORD = DATA / "secrets" / "nas-sync-password"
LOG = DATA / "run" / "nas.log"

# never leaves the Mac: secrets, the pinned harness (re-downloadable), build scratch, the served copy (synced separately)
BACKUP_EXCLUDES = ["/secrets/", "/bin/", "/run/stage/", "/run/farm/", "/site/", "/site.new/", "/site.old/",
                   "/run/*/check/"]
# in an artist's root: Claude Code's own caches; the transcripts under .config/projects stay
ROOT_EXCLUDES = [".config/backups/", ".config/policy-limits*", ".config/remote-settings.json", "Library/", "studio/bin/",
                 "studio/out/easel/*.sock"]


# DSM's own folders in every share (recycle bin, thumbnails): never touched, never deleted
SYNOLOGY_OWN = ["--exclude=#recycle", "--exclude=@eaDir", "--exclude=#snapshot"]


def settings() -> dict | None:
    if not (SETTINGS.exists() and PASSWORD.exists()):
        return None
    s = {"user": "atelier-sync", "site": "atelier-site", "backup": "atelier-backup"} | json.loads(SETTINGS.read_text())
    return s if s.get("host") else None


def note(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def rsync(args: list[str], what: str, timeout: int) -> bool:
    PASSWORD.chmod(0o600)  # rsync refuses a password file others can read
    # no --mkpath: DSM's rsync is older; every destination is one folder below the share, which rsync makes itself
    r = subprocess.run([RSYNC, "-rltp", "--chmod=D755,F644", *SYNOLOGY_OWN, f"--password-file={PASSWORD}", "--timeout=60", *args],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        note(f"{what} failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-400:]}")
        return False
    note(f"{what}: ok")
    return True


def url(s: dict, module: str, sub: str = "") -> str:
    return f"rsync://{s['user']}@{s['host']}/{s[module]}/{sub}"


def sync_site() -> bool | None:
    """The published site, as one consistent state: new files land at the end, together; stale ones go after."""
    s = settings()
    if not s:
        return None
    site = DATA / "site"
    if not site.exists():
        return None
    return rsync(["--delete-delay", "--delay-updates", f"{site}/", url(s, "site")], "site sync", 600)


def backup() -> bool | None:
    """The atelier's records and every artist's root (studio, notebook, transcripts), mirrored."""
    s = settings()
    if not s:
        return None
    ok = rsync(["--delete", *[f"--exclude={e}" for e in BACKUP_EXCLUDES], f"{DATA}/", url(s, "backup", "data/")],
               "backup data", 3600)
    reg = DATA / "artists.json"
    for a, rec in sorted((json.loads(reg.read_text()) if reg.exists() else {}).items()):
        root = Path(rec["root"])
        if root.exists():
            ok &= rsync(["--delete", *[f"--exclude={e}" for e in ROOT_EXCLUDES], f"{root}/", url(s, "backup", f"root-{a}/")],
                        f"backup root {a}", 3600)
    return ok
