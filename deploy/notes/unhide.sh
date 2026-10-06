#!/bin/sh
# Make a hidden note visible again. Usage: ./unhide.sh <id>
# Same requirements as hide.sh.
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
  ''|*[!0-9]*) echo "usage: $0 <note id>" >&2; exit 2 ;;
esac
npx wrangler d1 execute "${NOTES_DB:-atelier-notes}" --remote \
  --command "UPDATE notes SET hidden = 0 WHERE id = $1; SELECT id, at, work, hidden, text FROM notes WHERE id = $1;"
