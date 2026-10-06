# The public site on the NAS

nginx serves `site/`; cloudflared opens an outbound tunnel to Cloudflare, which serves
https://notart.fyi. The NAS publishes no ports and the router stays closed. nginx keeps no access log.

## Once: the tunnel (Cloudflare dashboard, the owner)

1. dash.cloudflare.com -> **Zero Trust** (first time: pick the Free plan, a team name of your
   choice; no card is needed for Free, skip if it asks for one and choose another way or stop) ->
   **Networks -> Tunnels -> Create a tunnel -> Cloudflared**, name `atelier`, Save.
2. On "Install and run connectors", choose **Docker**, copy the whole command shown, then on the Mac:
   `bash ~/dev/atelier/tools/save-token.sh tunnel` (it waits; copy the command when it asks, press Enter).
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
- Security -> Bots: **Block AI bots** on (robots.txt asks too; this enforces it).
- No analytics, no Web Analytics beacon: the site counts nobody.

## Updating the site

Replace the contents of `docker/atelier/site`; nginx serves them at once (no restart). The export's
automatic sync (`DATA/sync.sh`) comes with milestone 2.
