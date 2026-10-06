#!/bin/bash
# Saves the artists' Claude Code login token without ever showing it (requirements: operations.md, the login).
#
#   1. in Terminal: claude setup-token         (prints the token once)
#   2. in Terminal: bash tools/save-token.sh
#   3. when it asks: copy the token, from sk-ant- to its end, then press Enter
#
#   bash tools/save-token.sh tunnel             the Cloudflare Tunnel token instead (starts eyJ), saved as
#                                               ~/atelier-data/secrets/tunnel.env for the NAS (deploy/nas)
#
# Copying the token only after this script waits matters: copying this command would otherwise
# replace the token on the clipboard. Lines the terminal wrapped are joined; the clipboard is cleared.
set -euo pipefail
if [ "${1:-}" = tunnel ]; then
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/tunnel.env}"; start=eyJ; re='eyJ[A-Za-z0-9_=+/-]{100,}'; pre=TUNNEL_TOKEN=
else
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/claude-oauth-token}"; start=sk-ant-; re='sk-ant-[A-Za-z0-9_-]{40,}'; pre=
fi

read -rp "Copy the token now (from $start to its end), then press Enter here... " _
# a paragraph at a time: the token's wrapped lines join, the text around it stays apart
t=$(pbpaste | awk -v RS= '{ gsub(/[ \t]*\r?\n[ \t]*/, ""); print }' | grep -oE "$re" | head -1 || true)
if [ -z "$t" ]; then
  echo "No token on the clipboard (nothing saved). Copy it from the setup-token output and run this again."
  exit 1
fi
umask 077
mkdir -p "$(dirname "$f")"
if [ -n "$pre" ]; then printf '%s%s\n' "$pre" "$t"; else printf '%s' "$t"; fi > "$f.tmp"
mv "$f.tmp" "$f"
chmod 600 "$f"
printf '' | pbcopy
echo "Saved to $f: ${#t} characters, starting $start. The clipboard is cleared."
