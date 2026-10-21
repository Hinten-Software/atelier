#!/bin/bash
# After a merge from upstream: every finished painting must still replay to exactly the picture on its wall (NFR-1,
# REC-4). A painting's log names its engine, width and box; the replay easel (engine/target/release/easel, built by
# tools/build-engine.sh) must paint the same pixels from it, byte for byte, or the merge is not taken.
#
#   bash tools/upstream/verify.sh [<work id> ...]      default: every finished work in the store
#
# Prints one line per work and "verify: ok" or "verify: N DIFFER" last; exit 1 if any differs or fails.
set -uo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
DATA=${ATELIER_DATA:-$HOME/atelier-data}
easel=$repo/engine/target/release/easel
[ -x "$easel" ] || { echo "verify: no replay easel at $easel (bash tools/build-engine.sh)" >&2; exit 2; }
jobs=${VERIFY_JOBS:-1}  # one at a time: each replay at 4800 px takes the machine's cores for 10-15 minutes
scratch=$(mktemp -d "${TMPDIR:-/tmp}/atelier-verify.XXXXXX")
trap 'rm -rf "$scratch"' EXIT

one() {  # replays one work's log in a room of its own, then compares with the painting that hangs
  local id=$1 pkg=$DATA/works/$1 w=$scratch/$1
  mkdir -p "$w/paintings/lua" "$w/out/easel/painting" "$w/notes"
  cp "$pkg/painting.lua" "$w/paintings/lua/painting.lua"
  cp "$pkg/painting.lua" "$w/out/easel/painting/committed.lua"
  local t0=$SECONDS out
  # the session is the log's own name, "painting", in a room of its own (EASEL_ROOT): since claude-paint 693f49f a
  # session opened as "painting" is not found under another name, and a save that fails must say so, not "DIFFERS"
  if ! out=$(cd "$w" && EASEL_ROOT="$w" EASEL_SESSION=painting nice -n 10 "$easel" open painting 2>&1); then
    echo "FAIL    $id: the log doesn't reopen: $(echo "$out" | tail -1)"; return
  fi
  if ! out=$(cd "$w" && EASEL_ROOT="$w" EASEL_SESSION=painting "$easel" save "$w/replayed.png" 2>&1); then
    echo "FAIL    $id: the replay couldn't be saved: $(echo "$out" | tail -1)"
  elif cmp -s "$w/replayed.png" "$pkg/final.png"; then echo "same    $id ($((SECONDS - t0)) s)"
  else echo "DIFFERS $id ($((SECONDS - t0)) s)"; fi
  (cd "$w" && EASEL_ROOT="$w" EASEL_SESSION=painting "$easel" close >/dev/null 2>&1)
}
export -f one; export DATA easel scratch

if [ $# -gt 0 ]; then ids=("$@"); else
  ids=(); for m in "$DATA"/works/*/manifest.json; do
    d=$(dirname "$m"); [ -f "$d/final.png" ] && [ -f "$d/painting.lua" ] && ids+=("$(basename "$d")")
  done
fi
echo "verify: ${#ids[@]} paintings with $easel ($(shasum -a 256 "$easel" | cut -c1-12))"
printf '%s\n' "${ids[@]}" | xargs -P "$jobs" -I{} bash -c 'one {}' | tee "$scratch/out"
bad=$(grep -cv '^same' "$scratch/out")
[ "$bad" = 0 ] && { echo "verify: ok"; exit 0; }
echo "verify: $bad DIFFER or FAIL"; exit 1
