# The public site on the NAS

nginx serves `site/`; cloudflared opens an outbound tunnel to Cloudflare, which serves
https://notart.fyi. The NAS publishes no ports and the router stays closed. nginx keeps no access log.

## Once: the tunnel (Cloudflare dashboard, the owner)

1. dash.cloudflare.com -> **Zero Trust** (first time: a team name of your choice, the Free plan;
   Cloudflare may ask for a payment method even for the $0 plan, which is your call) ->
   **Networks -> Tunnels -> Create a tunnel -> Cloudflared**, name `atelier`, Save.
2. On "Install and run connectors", choose **Docker**, copy the whole command shown, then on the Mac:
   `bash ~/dev/atelier/tools/save-token.sh tunnel` (it waits; copy the command when it asks, press Enter).
   No clipboard on the Mac (e.g. a remote session): paste or type the token into a plain-text file and run
   `bash ~/dev/atelier/tools/save-token.sh tunnel FILE`; the token is checked and FILE deleted.
   This writes `~/atelier-data/secrets/tunnel.env`. Click **Next**.
3. **Public hostname**: subdomain empty, domain `notart.fyi`, path empty; service **HTTP**, URL `web:80`.
   Save. (Optional, same tunnel: a second hostname `www` -> `web:80`.)

## Once: the NAS (DSM, the owner)

1. File Station: create `docker/atelier`, upload into it `compose.yaml`, `nginx.conf`, the `site`
   folder, and `~/atelier-data/secrets/tunnel.env` (in Finder: Cmd-Shift-G, `~/atelier-data/secrets`).
2. Container Manager -> **Project -> Create**: name `atelier`, path `/docker/atelier`, source
   "Use existing docker-compose.yml". Next, skip Web Station, Done. Both containers should run.
3. The tunnel shows **Healthy** in the dashboard, and https://notart.fyi shows the page.

## Cloudflare settings for notart.fyi (recommended)

- SSL/TLS -> Edge Certificates: **Always Use HTTPS** on.
- Security -> Bots (AI Crawl Control): Training **Block**, Search **Allow**, Agent **Allow**; robots.txt
  says the same. Training is what matters: published thought processes must not teach future models
  that they are watched.
- No analytics, no Web Analytics beacon: the site counts nobody.

## The faucet: the live feed from the Mac (DSM, the owner, once)

nginx serves the shared folder `atelier-site`; the Mac syncs the export into it every two minutes
while a work paints, through DSM's rsync service and a user that can write nowhere else. (SSH on DSM is
for administrators only, so the sync user does not get SSH.)

1. Control Panel -> Shared Folder -> Create: `atelier-site`. Then a second one: `atelier-backup`.
2. Control Panel -> File Services -> rsync: **Enable rsync service** (port 873). Nothing else there.
3. Control Panel -> User & Group -> Create: `atelier-sync`, a long password of your choice, no email.
   Groups: `users` only. Shared folder permissions: `atelier-site` and `atelier-backup` **Read/Write**,
   every other folder **No access**. Applications: **rsync** allowed, everything else denied. No quota.
4. On the Mac: `bash ~/dev/atelier/tools/save-token.sh nas` (copy the password when it asks), or with
   a text file as for the tunnel: `... save-token.sh nas FILE`.
5. Re-upload `compose.yaml` (its volume now points at `/volume1/atelier-site`) and in Container Manager
   -> Project -> atelier -> Action -> **Build** (recreates the containers). Until the first sync lands,
   the page is empty: put the `site` folder's files into `atelier-site` once by hand, or wait.
6. Snapshot Replication (Package Center): daily snapshots of both shared folders, keep 30. The Mac can
   write the folders, but only the NAS can delete snapshots.

## The drain: backups

`tools/backup.sh` (milestone 2) copies the studios and the atelier's data (never the secrets) to
`atelier-backup` daily after the painting window closes and after every finished work. Offsite copies:
Hyper Backup from the NAS to a cloud of the owner's choice (requirements Q9).
