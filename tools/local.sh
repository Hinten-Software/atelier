#!/bin/bash
# The atelier's private store for painters on a local model (the owner, 2026-10-22: a couple of test runs in private
# before anything is public). Everything here is the runner as usual, with ATELIER_DATA set to ~/atelier-local: a store
# with no nas.json, so tools/push.sh never pushes it, the tick never sees it, and its export stays on this Mac.
#
#   tools/local.sh probes --local google/gemma-4-e4b       the probe suite against the local model (RUN-16)
#   tools/local.sh birth --local google/gemma-4-e4b --studio iv    a painter on it (iv: not to be confused with I-III)
#   tools/local.sh paint iv --by owner                     a work (any hour: no painting window here)
#   tools/local.sh status | resume | export | ...          as `atelier`
#   tools/local.sh serve                                   the private export on http://127.0.0.1:8801/studio/ only
#
# LM Studio's server must be on (its Developer tab, or ~/.lmstudio/bin/lms server start) with the model loaded at a
# context of at least 49152 tokens, with no idle unloading (its TTL); until it is, a work waits, trying every 10 minutes.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY=/opt/homebrew/opt/python@3.13/libexec/bin/python3  # the runner's Python, with Pillow (as the tick's plist)
export ATELIER_DATA="${ATELIER_LOCAL_DATA:-$HOME/atelier-local}"
export ATELIER_WINDOW=always
unset ATELIER_WORK  # the export builds in this store, never in a folder that is pushed
PINNED="$HOME/atelier-data/bin"

if [ -f "$ATELIER_DATA/nas.json" ]; then
  echo "$ATELIER_DATA has a nas.json: it would be pushed to the NAS; not using it" >&2
  exit 1
fi
mkdir -p "$ATELIER_DATA/bin" "$ATELIER_DATA/run"
chmod 700 "$ATELIER_DATA"
for f in "$PINNED"/claude-*; do  # the pinned Claude Code (RUN-15), the same copy the public store uses
  [ -e "$ATELIER_DATA/bin/$(basename "$f")" ] || ln -s "$f" "$ATELIER_DATA/bin/"
done

cmd="${1:-status}"
[ $# -gt 0 ] && shift
case "$cmd" in
  probes) exec "$PY" "$REPO/runner/probes.py" "$@" ;;
  serve)  exec "$PY" "$REPO/runner/atelier.py" serve --host 127.0.0.1 --port 8801 "$@" ;;
  *)      exec "$PY" "$REPO/runner/atelier.py" "$cmd" "$@" ;;
esac
