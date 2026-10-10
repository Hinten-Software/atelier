#!/bin/bash
# Read access for the NAS's sharing user (docs/design-nas-publisher.md, requirements OPS-8): the store and the
# artists' roots, read-only, by ACL, inherited by everything written there later. Nothing else of this Mac.
#
#   bash tools/share-setup.sh            after creating the Sharing Only user atelier-nas
#   bash tools/share-setup.sh --check    what the user can read, changing nothing
#
# The store and the roots are mode 700 and stay so; the ACL is the only way in. File Sharing's own "Read Only"
# for the user is the second guard. Run it again any time: an ACL already there is not added twice.
set -euo pipefail
U=atelier-nas
DATA="${ATELIER_DATA:-$HOME/atelier-data}"
READ="list,search,readattr,readextattr,readsecurity,read,file_inherit,directory_inherit"

id "$U" >/dev/null 2>&1 || { echo "no user $U: create it first (System Settings -> Users & Groups -> Sharing Only)"; exit 1; }
[ -e "$DATA/secrets" ] && { echo "$DATA/secrets still exists: the secrets live in ~/.atelier/secrets now; remove it first"; exit 1; }
roots=$(/usr/bin/python3 -c "import json,sys; print('\n'.join(r['root'] for r in json.load(open(sys.argv[1])).values()))" "$DATA/artists.json")

has() { ls -led "$1" | grep -q "user:$U allow"; }
if [ "${1:-}" = --check ]; then
  for d in "$DATA" $roots; do has "$d" && echo "readable: $d" || echo "NOT readable: $d"; done
  exit 0
fi

# the way in: search (not list) through the folders above, so the user can reach the shares and see nothing else.
# Only where it is closed: /Users/Shared is the system's and open to everyone already (drwxrwxrwt)
for d in "$HOME" /Users/Shared; do
  if has "$d" || [ "$(stat -f %Sp "$d" | cut -c10)" != - ]; then continue; fi  # 10th: others may search
  chmod +a "$U allow search" "$d"
done
for d in "$DATA" $roots; do
  if has "$d"; then echo "already readable: $d"; continue; fi
  chmod -R +a "$U allow $READ" "$d"
  echo "readable: $d"
done
