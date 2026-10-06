#!/bin/sh
# Hide a note (spam or illegal content). Usage: ./hide.sh <id>
# Needs wrangler.toml next to this script and a logged-in wrangler
# (or CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID). Database name can be
# overridden with NOTES_DB.
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
  ''|*[!0-9]*) echo "usage: $0 <note id>" >&2; exit 2 ;;
esac
npx wrangler d1 execute "${NOTES_DB:-atelier-notes}" --remote \
  --command "UPDATE notes SET hidden = 1 WHERE id = $1; SELECT id, at, work, hidden, text FROM notes WHERE id = $1;"
