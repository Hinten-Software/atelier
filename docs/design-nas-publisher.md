# The Mac paints, the NAS does the rest

2026-10-10. Design, not built yet. Decided by the owner: the Mac is the painter and nothing more; everything
after the brush stroke (export, site, backups) moves to the NAS, and the NAS fetches from the Mac over SMB.

## Why

Since 2026-10-07 23:11 every sync and backup the runner started failed with `No route to host`; only the ones run
by hand from a terminal got through. macOS (15 and later) blocks a LaunchAgent's own connections to the home network
unless its program is approved under Local Network, and blocks its access to network volumes under Network Volumes /
Full Disk Access. Tested on 2026-10-10 with throwaway launchd jobs:

| started by launchd | result |
|---|---|
| Homebrew `python3` -> NAS:873 | `No route to host` |
| `Python.app/Contents/MacOS/Python` -> NAS:873 (the app on the Local Network list, toggled off and on) | `No route to host`, no prompt |
| `/opt/homebrew/bin/rsync` -> NAS:873 | `No route to host` |
| `/bin/sh` writing to `/Volumes/atelier-site` (SMB mount) | `Operation not permitted` |

Homebrew's Python is ad-hoc signed (`Identifier=Python-<hash>`), so an approval, if one took, would not survive the
next `brew upgrade`. Nothing on the Mac that runs unattended can be relied on to reach the NAS.

Incoming connections are different: macOS File Sharing (smbd) is part of the system and serves whoever it is
configured for. So the direction turns around. The Mac never connects to the NAS; the NAS reads from the Mac.

## The split

**The Mac: the painter.**
- Sittings: Claude Code, the easel, the engine.
- The runner's live part: preparing and starting works, sittings, the live white-room audit (it must stop a
  sitting at once), budget and window, the replay check and the package when a work ends (REC-1, REC-4).
- `atelier tick` (LaunchAgent), unchanged. It touches no network.
- Writes everything to `~/atelier-data` and the artists' roots, as now. No export, no sync, no backup.
- Shares, read-only, to one NAS user: `~/atelier-data` and each artist's root.

**The NAS: everything after.**
- DSM mounts the Mac's shares (File Station -> Tools -> Mount Remote Folder -> CIFS, mounted at startup).
- A new container `publisher` in the existing `atelier` project:
  - every 2 minutes (OPS-4, REC-3): the export, its scan and allowlist, then the result into `atelier-site`;
  - after a work's state changes (a sitting ends, a work hangs) and once a night at 07:15: the backup into
    `atelier-backup`.
- nginx, cloudflared, Gitea, snapshots and Hyper Backup as they are.

```
Mac (painter)                                   NAS
~/atelier-data  ──SMB, read-only──▶  /volume1/mac/atelier-data ─┐
the three roots ──SMB, ro──▶  /volume1/mac/roots/…             ─┤
                                                                ▼
                                                  publisher ──▶ atelier-site ──▶ nginx ──▶ tunnel
                                                            └─▶ atelier-backup (snapshots, Hyper Backup)
```

## On the Mac

1. **Secrets out of the shared store.** `DATA/secrets/` moves to `~/.atelier/secrets/` (next to the private word
   list, which is already outside), so nothing shared holds a secret and no ACL has to keep one out. `bin/` (the
   pinned Claude Code) stays in DATA; the publisher ignores it.
2. **A sharing-only user** `atelier-nas` (System Settings -> Users & Groups -> Sharing Only), long password, no
   login, no home.
3. **File Sharing on**, SMB only, with shares `atelier-data` (`~/atelier-data`) and `studio-i`, `studio-ii`,
   `studio-iii` (the three roots), each Read Only for `atelier-nas`, No Access for everyone else. The folders are
   mode 700; `atelier-nas` gets read access by ACL (`chmod +a "atelier-nas allow read,readattr,readextattr,
   readsecurity,list,search,file_inherit,directory_inherit"`), set by `tools/share-setup.sh` so it is on record.
4. The firewall is off today; if it is turned on, File Sharing must stay allowed.
5. The Mac must not sleep while it shares; it does not sleep today (no sleep since boot) and OPS-6 keeps it awake
   during a work. A Mac that is away only delays the site; nothing is lost.

## On the NAS

- **Mounts.** DSM mounts each share read-only as `atelier-nas`, with "mount automatically on startup", under
  `/volume1/mac/`. The roots' folder is mounted into the container at `/Users/Shared`, each root at its Mac path, so the
  transcript paths in `run/*/state.json` resolve without any mapping; `atelier-data` is mounted at `/data`
  (`ATELIER_DATA=/data`).
- **The image.** `deploy/nas/publisher/Dockerfile`: Python 3.13 slim, Pillow, rsync, and the repository's
  `runner/` (export, audit, config), `viewer/` and `site/`. Built in Container Manager from a checkout of `main`
  out of Gitea; an update is `git pull` and Build, like the other containers.
- **The loop** (`runner/publish.py`, new): every 120 s, if anything under `/data/run` or `/data/works` changed,
  run the export into the container's own work folder (`/work`: farm, stage), then
  `rsync --delete-delay --delay-updates /work/site/ /site/` into `atelier-site` (local copy, same consistency as
  today: new files land together, stale ones go after). nginx keeps its read-only mount of the same folder.
- **Backups.** The same rsync and excludes as `runner/nas.py` today, local on the NAS: `/data` -> `atelier-backup/data`,
  each root -> `atelier-backup/root-<studio>`. Triggered by a changed `run/*/state.json` (a sitting ended, a work
  hung) and nightly at 07:15. OPS-2's "after every sitting" holds.
- **Private settings** in `/volume1/docker/atelier/publisher.env` and `private-words.txt`, never in the repository:
  the Mac's home path and account name (the export scrubs and scans for them; today it takes them from the machine
  it runs on), and the private word list.
- **Status.** The publisher writes `status.json` (last export, last backup, a blocked export's redacted reasons)
  into `atelier-backup/status/`, and logs to the container log. `atelier status` on the Mac shows it when the share
  is reachable from where it runs (a terminal can; the tick does not need to).

## What changes in the repository

| where | change |
|---|---|
| `runner/config.py` | `TOKEN` and other secrets under `~/.atelier/secrets`; `SCRUB_HOME`, `SCRUB_USER` from the environment, defaulting to this machine's |
| `runner/export.py` | read the store from `ATELIER_DATA`, write farm, stage and site under `ATELIER_WORK` (the store is read-only on the NAS); `BLOCKED` into the status |
| `viewer/studio.py`, `runner/audit.py` | `HOME`/`USER` and the home-path pattern from `SCRUB_HOME`/`SCRUB_USER` |
| `runner/publish.py` | new: the NAS loop (export, copy into the site, backup triggers, status) |
| `runner/works.py` | `Exporter`, `export_now()` and the `nas.backup()` call go; the runner no longer exports |
| `runner/nas.py` | removed |
| `runner/atelier.py` | `sync`, `backup`, `serve` go; `export` stays for a local check (into a scratch folder, never published); `status` shows the publisher's status |
| `tools/save-token.sh` | writes to `~/.atelier/secrets`; the `nas` mode goes |
| `tools/share-setup.sh` | new: the ACLs for `atelier-nas` |
| `deploy/nas/` | `publisher/Dockerfile`, compose service `publisher`, README: mounts, user, env |
| `deploy/mac/` | README: File Sharing, the sharing user |
| tests | export with a read-only store and a separate work folder; publish loop with a fake store |
| docs | operations runbook; requirements below |

## Requirements that change

- **OPS-1** Painter host: the Mac, and only the painting (sittings, live audit, packaging). *(was: painter host)*
- **OPS-2** The NAS copies the private store and the artists' roots into the archive after every sitting and
  nightly, reading the Mac's read-only shares. *(was: the store is synced to the NAS)*
- **OPS-4** During a live work, the NAS exports every 2 minutes. *(was: export and push)*
- **OPS-8** The Mac shares the store and the roots read-only to one sharing-only user; it holds no NAS
  credential and opens no connection to the NAS. nginx serves a read-only mount of the site folder as before.
  *(was: the Mac pushes with a dedicated NAS user)*
- **REC-7** unchanged in substance; the scan's home path and account come from settings, since it no longer runs
  on the Mac.

## Changing over

1. Build and test the publisher against a copy of the store on the NAS, with the Mac's current push still in place.
2. Mac: move the secrets, create `atelier-nas`, the shares and ACLs. NAS: mounts, `publisher.env`, start the
   publisher writing to a scratch folder; compare its export with the Mac's, file by file.
3. Point the publisher at `atelier-site`, remove the runner's export and push (one commit), log it in history.md.
4. Delete the NAS user `atelier-sync` and its rsync permission; turn DSM's rsync service off if nothing else uses it.

Do it in the day, outside the painting window; a work in progress keeps painting through all of it.

## Open questions

- **LAN preview.** `atelier serve` goes with the export. If a preview inside the house is still wanted, nginx can
  also listen on a LAN port of the NAS (not through the tunnel). Default: no.
- **Reading a live transcript over SMB.** The export reads transcripts while Claude Code appends to them; a last
  line can be half-written. The viewer's parser reads only up to the last newline
  (`viewer/studio.py:267`), so a half-written line waits for the next round; SMB's caching of a file another
  machine is appending to is to be confirmed in step 2.
- **Load.** The store is 2.5 GB today; the export reads only the open work's transcripts and what changed. To
  watch in step 2: the NAS's CPU during an export, and SMB traffic.
