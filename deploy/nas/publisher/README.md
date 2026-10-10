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
