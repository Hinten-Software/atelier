#!/bin/bash
# Saves the artists' Claude Code login token without ever showing it (requirements: operations.md, the login).
#
#   1. in Terminal: claude setup-token         (prints the token once)
#   2. in Terminal: bash tools/save-token.sh
#   3. when it asks: copy the token, from sk-ant- to its end, then press Enter
#
#   bash tools/save-token.sh tunnel             the Cloudflare Tunnel token instead (starts eyJ), saved as
#                                               ~/atelier-data/secrets/tunnel.env for the NAS (deploy/nas)
#   bash tools/save-token.sh tunnel FILE        read the token from FILE instead of the clipboard (for a
#                                               token typed or pasted there); FILE is deleted after saving
#   bash tools/save-token.sh turnstile [FILE]   the Turnstile widget's secret key (deploy/notes), starts 0x
#   bash tools/save-token.sh cloudflare [FILE]  the Cloudflare API token that deploys the notes service
#   bash tools/save-token.sh nas [FILE]         the NAS sync user's password (deploy/nas), saved as
#                                               ~/atelier-data/secrets/nas-sync-password
#
# Copying the token only after this script waits matters: copying this command would otherwise
# replace the token on the clipboard. Lines the terminal wrapped are joined; the clipboard is cleared.
set -euo pipefail
if [ "${1:-}" = tunnel ]; then
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/tunnel.env}"; start=eyJ; re='eyJ[A-Za-z0-9_=+/-]{100,}'; pre=TUNNEL_TOKEN=
elif [ "${1:-}" = turnstile ]; then
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/turnstile-secret}"; start="0x"; re='0x[A-Za-z0-9_-]{20,}'; pre=
elif [ "${1:-}" = cloudflare ]; then
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/cloudflare-api-token}"; start="its first character"; re='[A-Za-z0-9_-]{30,}'; pre=
elif [ "${1:-}" = nas ]; then
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/nas-sync-password}"; start="its first character"; re='[^[:space:]]{8,}'; pre=
else
  f="${ATELIER_TOKEN_FILE:-$HOME/atelier-data/secrets/claude-oauth-token}"; start=sk-ant-; re='sk-ant-[A-Za-z0-9_-]{40,}'; pre=
fi

src="${2:-}"
if [ -z "$src" ]; then
  read -rp "Copy the token now (from $start to its end), then press Enter here... " _
fi
source_text() { if [ -n "$src" ]; then cat "$src"; else pbpaste; fi; }
# a paragraph at a time: the token's wrapped lines join, the text around it stays apart
t=$(source_text | awk -v RS= '{ gsub(/[ \t]*\r?\n[ \t]*/, ""); print }' | grep -oE "$re" | head -1 || true)
if [ -z "$t" ]; then
  echo "No token found (nothing saved). Check it starts with $start and run this again."
  exit 1
fi
if [ "$start" = eyJ ]; then
  # a tunnel token is base64 JSON with the account (a), the tunnel id (t) and its secret (s): a typo breaks it
  if ! printf '%s' "$t" | python3 -c '
import base64, json, re, sys
t = sys.stdin.read().strip()
d = json.loads(base64.b64decode(t + "=" * (-len(t) % 4)))
assert set(d) >= {"a", "t", "s"} and re.fullmatch(r"[0-9a-f]{32}", d["a"]) and re.fullmatch(r"[0-9a-f-]{36}", d["t"])
' 2>/dev/null; then
    echo "The token is incomplete or has a typo (nothing saved). Fix it and run this again."
    exit 1
  fi
fi
umask 077
mkdir -p "$(dirname "$f")"
if [ -n "$pre" ]; then printf '%s%s\n' "$pre" "$t"; else printf '%s' "$t"; fi > "$f.tmp"
mv "$f.tmp" "$f"
chmod 600 "$f"
if [ -n "$src" ]; then rm -P "$src" 2>/dev/null || rm -f "$src"; else printf '' | pbcopy; fi
echo "Saved to $f: ${#t} characters, starting $start. Checked; the source is cleared."
