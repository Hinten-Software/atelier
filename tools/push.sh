#!/bin/bash
# The Mac's copy to the NAS (requirements OPS-2, OPS-4): the published site every run, the backup at most every
# 30 minutes. Run by launchd (deploy/mac/atelier.push.plist, every 2 minutes).
#
#   bash tools/push.sh            site, and the backup if 30 minutes have passed
#   bash tools/push.sh backup     site and backup now
#
# Why a shell script and Apple's /usr/bin/rsync (2026-10-10, tested): macOS lets a LaunchAgent reach the home network
# through Apple's own programs, not through Homebrew's python or rsync, and a connection counts as the program's that
# started it. So no python in this chain. Settings: DATA/nas.json {"host": ...}; password: ~/.atelier/secrets.
set -uo pipefail
DATA="${ATELIER_DATA:-$HOME/atelier-data}"
PASSWORD="${ATELIER_SECRETS:-$HOME/.atelier/secrets}/nas-sync-password"
LOG="$DATA/run/nas.log"
STAMP="$DATA/run/backup-at"
[ -f "$DATA/nas.json" ] && [ -f "$PASSWORD" ] || exit 0  # no NAS configured: nothing to do
HOST=$(/usr/bin/plutil -extract host raw -o - "$DATA/nas.json")
USER_=$(/usr/bin/plutil -extract user raw -o - "$DATA/nas.json" 2>/dev/null || echo atelier-sync)
export RSYNC_PASSWORD="$(cat "$PASSWORD")"
# DSM's own folders in every share (recycle bin, thumbnails): never touched, never deleted
OWN=(--exclude='#recycle' --exclude=@eaDir --exclude='#snapshot')

note() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
copy() {  # what, then rsync's arguments
  local what=$1; shift
  if out=$(/usr/bin/rsync -rltp "${OWN[@]}" --timeout=60 "$@" 2>&1); then note "$what: ok"; else note "$what failed: ${out: -400}"; fi
}

# the site, as one consistent state: new files land at the end, together; stale ones go after
[ -d "$DATA/site" ] && copy "site sync" --delete-delay --delay-updates "$DATA/site/" "rsync://$USER_@$HOST/atelier-site/"

if [ "${1:-}" = backup ] || [ ! -f "$STAMP" ] || [ -n "$(find "$STAMP" -mmin +30)" ]; then
  touch "$STAMP"
  # never leaves the Mac: the pinned harness (re-downloadable), build scratch, the served copy (synced above)
  copy "backup data" --delete --exclude=/bin/ --exclude=/run/stage/ --exclude=/run/farm/ --exclude=/site/ \
    --exclude=/site.new/ --exclude=/site.old/ --exclude='/run/*/check/' "$DATA/" "rsync://$USER_@$HOST/atelier-backup/data/"
  # each artist's root (studio, notebook, transcripts); Claude Code's own caches stay
  /usr/bin/python3 -c 'import json,sys; [print(k, v["root"]) for k, v in json.load(open(sys.argv[1])).items()]' "$DATA/artists.json" |
  while read -r id root; do
    copy "backup root $id" --delete --exclude=/.config/backups/ --exclude='/.config/policy-limits*' \
      --exclude=/.config/remote-settings.json --exclude=/Library/ --exclude=/studio/bin/ --exclude='/studio/out/easel/*.sock' \
      "$root/" "rsync://$USER_@$HOST/atelier-backup/root-$id/"
  done
fi
