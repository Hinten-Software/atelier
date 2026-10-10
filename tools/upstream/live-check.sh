#!/bin/bash
# After a merge from upstream and a build: does a painting made with the painter's easel, with the newest tools, still
# replay byte for byte with the replay easel (what decides whether a work hangs: REC-4, engine/scripts/check_painting)?
#
#   bash tools/upstream/live-check.sh [<box>]        default: every
#
# Paints a few chunks in a throwaway studio under /Users/Shared/atelier (a 4800 px canvas, brushes, the rag, thinned
# paint, waiting for paint to dry, the scratch canvas), closes the easel, and runs check_painting. Last line: its verdict.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
box=${1:-every}
easel=$repo/engine/target/painter/boxes/$box/easel
[ -x "$easel" ] || { echo "live-check: no painter's easel for $box (bash tools/build-engine.sh)" >&2; exit 2; }
s=$(mktemp -d /Users/Shared/atelier/live-check.XXXXXX)
trap '"$s/bin/easel" close >/dev/null 2>&1 || true; rm -rf "$s"' EXIT
mkdir -p "$s/bin" "$s/paintings/lua" "$s/notes"
cp "$easel" "$s/bin/easel"
E() { (cd "$s" && "$s/bin/easel" "$@"); }
chunk() { E do - <<<"$1" | tail -1; }
E open >/dev/null
chunk 'canvas{size=300, aspect=1.25, linen=18, seed=11, ground={{pile={{"lead white", 3}, {"yellow ochre", 1}}, um=60, apply="knife", texture=0.3}}}'
chunk 'local t = tubes(); p = pile{{t[1], 2}, {t[#t], 1}}; q = pile{{t[2], 1}, thinner=0.5}
b = brush("filbert", 9); b:load(p, 0.8); b:stroke({{120, 600}, {420, 300}, {800, 260}}, {pressure={0.9, 0.4}})
work(rect(100, 100, 400, 250), {hand="glaze", pile=q})'
chunk 'r = rag(); r:wipe(ellipse(500, 400, 160, 90), {pressure=0.6}); r:blot(300, 500, {pressure=0.5})'
chunk 'print(wait(3 * 60)); b:reload(p, 0.6); b:stroke({{200, 700}, {700, 650}}); print(drying(300, 500))'
chunk 'x = pile{{tubes()[1], 1}}; b = brush("round", 4); b:load(x, 0.5); b:stroke({{50, 50}, {250, 150}})' >/dev/null
E do --scratch - <<<'b = brush("round", 4)' >/dev/null
echo "painted: $(grep -c '^--@ chunk' "$s/paintings/lua/painting.lua") chunks, $(grep -E '^--@ (engine|width|box) ' "$s/paintings/lua/painting.lua" | tr '\n' ' ')"
E close >/dev/null
EASEL_NO_BUILD=1 "$repo/engine/scripts/check_painting" "$s" "$s.check" | tail -1
rm -rf "$s.check"
