# The publisher

The NAS's half of docs/design-nas-publisher.md: `runner/publish.py` in a container. It reads the Mac's store and
the artists' roots read-only, exports the site into a folder of its own, copies it into the folder nginx serves,
and backs the store and the roots up. It needs no network: it only reads and writes folders.

| in the container | what |
|---|---|
| `/data` (read-only) | the Mac's `~/atelier-data` |
| `/Users/Shared` (read-only) | the folder that holds the artists' roots, so each root is at its Mac path |
| `/work` | the publisher's own: the session farm, the stage, the last clean export |
| `/site` | what nginx serves (`atelier-site`) |
| `/backup` | the archive (`atelier-backup`); `status/status.json` says what happened last |
| `/config/private-words.txt` | the private word list (REC-7), the same as the Mac's `~/.atelier/private-words.txt` |

`publisher.env`, next to the compose file and never in the repository:

```
ATELIER_SCRUB_HOME=/Users/<the Mac's account>
TZ=<the Mac's time zone, e.g. Europe/Berlin>
```

The export scrubs and scans for that home path and account name; on the Mac it took them from the machine itself.
`TZ` puts the nightly backup (ATELIER_BACKUP_AT, 07:15) and the status's times on the painter's clock; without it
the container runs on UTC.

## Step 1: a test against a copy (the owner, once)

Nothing here touches `atelier-site` or `atelier-backup`; the Mac's own push goes on as before.

1. DSM: Control Panel -> Shared Folder -> Create `atelier-test` (no recycle bin). Your own account Read/Write.
2. The Mac, in Finder: Go -> Connect to Server -> `smb://<nas>/atelier-test`, as yourself. Then in a terminal
   (a terminal may reach the NAS; a LaunchAgent may not):

   ```
   rsync -rlt --exclude=/secrets/ --exclude=/bin/ ~/atelier-data/ /Volumes/atelier-test/data/
   sudo rsync -rlt /Users/Shared/<root>/ /Volumes/atelier-test/roots/<root>/     # each of the three roots
   ```

   (`sudo` because the roots are mode 700; the copy keeps no owner.)
3. File Station: create `docker/atelier-publisher-test`; in it, a checkout of `main` as `repo/` (or upload the
   repository's folder), `compose.test.yaml` from this folder renamed `compose.yaml`, `publisher.env`, and
   `private-words.txt`.
4. Container Manager -> Project -> Create: name `atelier-publisher-test`, path `/docker/atelier-publisher-test`,
   "Use existing docker-compose.yml". It builds the image and starts.
5. Check:
   - the container log shows `site copy: ok`, `backup data: ok`, and one `backup root <studio>: ok` for each studio;
   - `atelier-test/backup/status/status.json` has `"ok": true` for both;
   - `atelier-test/site/` is the same as the Mac's `~/atelier-data/site/`, file by file
     (`diff -r ~/atelier-data/site /Volumes/atelier-test/site` from the Mac terminal, after a fresh `atelier export`).
6. Stop the project. Step 2 (the Mac's shares instead of a copy) follows the design.

## Going live (the owner, with Claude for the checks)

**On the Mac**

1. System Settings -> Users & Groups -> Add User: **Sharing Only**, name `atelier-nas`, a long password of your
   own (it goes into DSM in step 6, nowhere else).
2. The old secrets folder goes: `rm -r ~/atelier-data/secrets` (the secrets are in `~/.atelier/secrets` since
   2026-10-10). Only once no runner from before that day is alive: a runner reads the token at every sitting.
3. `bash tools/share-setup.sh`, then `bash tools/share-setup.sh --check`: the store and the three roots readable.
4. System Settings -> General -> Sharing -> **File Sharing** on. (i):
   - Shared Folders: add `~/atelier-data` and each artist's root (`/Users/Shared/<root>`, from
     `~/atelier-data/artists.json`). For each: `atelier-nas` **Read Only**, Everyone **No Access**.
   - Options: **Share files and folders using SMB** on; under Windows File Sharing, tick `atelier-nas` and enter its
     password.

**On the NAS**

5. Control Panel -> Shared Folder -> Create `mac` (no recycle bin). In it, empty folders `atelier-data` and
   `roots/<root>` for each root.
6. File Station -> Tools -> **Mount Remote Folder** -> CIFS Shared Folder, once per share:
   `\\<the Mac's address>\atelier-data` -> `mac/atelier-data`, and each root -> `mac/roots/<root>`; account
   `atelier-nas`; **Mount automatically on startup** on.
7. Claude points the test project at those mounts and compares its export with the Mac's (as in step 1).
8. `docker/atelier`: put a checkout of `main` as `repo/`, `publisher.env` and `private-words.txt` (as in the test
   project), and the new `compose.yaml` from `deploy/nas/`.

**The switch** (in the day, outside the painting window)

9. Claude merges `publisher-live` (the runner stops exporting and pushing). Container Manager -> Project -> `atelier`
   -> Action -> **Build**: nginx, the tunnel and now the publisher. Within 2 minutes: `status.json` in
   `atelier-backup/status/` says `"ok": true`, and https://notart.fyi shows every work.
10. Stop and delete `atelier-publisher-test`; delete the `atelier-test` shared folder.

**Afterwards**

11. DSM: delete the user `atelier-sync`; Control Panel -> File Services -> rsync: off.
12. The Mac: delete `~/.atelier/secrets/nas-sync-password`, `~/atelier-data/nas.json`, `~/atelier-data/site`,
    `~/atelier-data/run/nas.log`. Log the change in `~/atelier-data/history.md`.
