#!/bin/bash
# Take a newer claude-paint onto the vendor branch `upstream` (one commit), ready for main to merge.
#
#   bash tools/upstream/import.sh [<ref>]      default: upstream's main
#   git merge upstream                          then: resolve, build, bash tools/upstream/verify.sh
#
# The branch `upstream` holds Alice's files and nothing else of ours changed: it started at e39267c (our first import,
# her a198dd0, byte for byte). Each import replaces the paths in map.txt with her version at <ref>. Her repository is
# only read (fetched into a cache, never built or run from here).
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
url=${CLAUDE_PAINT_URL:-https://github.com/aliceisjustplaying/claude-paint.git}
cache=${CLAUDE_PAINT_CACHE:-$HOME/.cache/atelier/claude-paint.git}
ref=${1:-main}

[ -d "$cache" ] || git clone -q --bare "$url" "$cache"
git -C "$cache" fetch -q --force --prune --tags origin '+refs/heads/*:refs/heads/*'
sha=$(git -C "$cache" rev-parse --verify "$ref^{commit}")
when=$(git -C "$cache" log -1 --format=%cs "$sha")
map=$(grep -v '^#' "$repo/tools/upstream/map.txt" | shasum | cut -c1-12)
last=$(git -C "$repo" log -1 --format=%B upstream | sed -n 's/^Upstream-Commit: //p')
lastmap=$(git -C "$repo" log -1 --format=%B upstream | sed -n 's/^Map: //p')
[ "$last" = "$sha" ] && [ "$lastmap" = "$map" ] && { echo "upstream is at $sha already, with this map"; exit 0; }

wt=$(mktemp -d "${TMPDIR:-/tmp}/atelier-upstream.XXXXXX")
trap 'git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 || true' EXIT
git -C "$repo" worktree add -q "$wt" upstream
grep -v '^#' "$repo/tools/upstream/map.txt" | while read -r src dst; do
  [ -n "$src" ] || continue
  rm -rf "${wt:?}/$dst"
  if git -C "$cache" cat-file -e "$sha:$src" 2>/dev/null; then
    mkdir -p "$wt/$(dirname "$dst")" "$wt/.in"
    git -C "$cache" archive "$sha" "$src" | tar -x -C "$wt/.in"
    mv "$wt/.in/$src" "$wt/$dst"
    rm -rf "$wt/.in"
  else
    echo "note: $src is gone upstream at $sha; removed here too" >&2
  fi
done
mkdir -p "$wt/tools/upstream" && echo "$sha" > "$wt/tools/upstream/commit"  # what main merged from (each work records it)
git -C "$wt" add -A
git -C "$wt" commit -q -m "upstream: claude-paint ${sha:0:7} ($when)" -m "Upstream-Commit: $sha
Map: $map" || { echo "nothing changed"; exit 0; }
echo "upstream: claude-paint ${sha:0:7} ($when) is on branch upstream. Next:"
echo "  git merge upstream    (in a worktree of your own while a work paints: the runner uses main's files)"
echo "  bash tools/build-engine.sh && bash tools/upstream/verify.sh"
