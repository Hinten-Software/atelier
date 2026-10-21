#!/usr/bin/env bash
# Build the replay easel and a painter's easel per box, with no account name or local path inside them (requirements ENG-7):
# rustc's panic locations and the Lua C sources' __FILE__ name the build machine's paths otherwise.
#   tools/build-engine.sh        -> engine/target/release/easel (the replay easel: the operator's, never in a studio)
#                                   engine/target/painter/boxes/<box>/{easel,studio,width,tubes.md}, a studio's bin/ per box
# Since claude-paint fea9aa6 the easel is one binary for every box; a file `studio` beside it ("painter <box>") makes
# it a painter's easel for that box, and `width` (4800) sets a new painting's width. The painter's binary is built with
# `--cfg atelier_painter`, which leaves out the one build path the replay easel keeps (ENG-7). The runner gives a
# studio its work's box's folder, "every" unless the owner names another (runner/config.py PAINTER_BOXES, DEFAULT_BOX).
# The boxes are paint's own (palette.rs BOXES), so a box upstream adds is set up here without a change.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo/engine"
cargo_home=${CARGO_HOME:-$HOME/.cargo}
remap="--remap-path-prefix=$cargo_home=/cargo --remap-path-prefix=$repo=/atelier --remap-path-prefix=$HOME=/home"
export RUSTFLAGS="$remap"
# the atelier's changes to the easel (the journal named "journal", no paper-and-pastel switch): on in what we build,
# off in a plain `cargo test`, so claude-paint's own tests hold unchanged (engine/crates/easel/src/main.rs ATELIER)
export ATELIER_BUILD=1
# byte-identical builds: the painter's easel paints, the replay easel (another build) must paint the same bytes from the
# log (REC-4). claude-paint's release profile is incremental since 2026-10-05 and accepts "bounded" drift between
# builds; ours is not (engine/Cargo.toml says so too since 2026-10-19, for builds made without this script)
export CARGO_PROFILE_RELEASE_INCREMENTAL=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
# engine/.cargo/config.toml sets CFLAGS for Lua's fixed hash seed; set here, it must carry that define too
export CFLAGS="-Dluai_makeseed()=0x5eedu -ffile-prefix-map=$cargo_home=/cargo -ffile-prefix-map=$HOME=/home"
cargo build --release -p easel
RUSTFLAGS="$remap --cfg atelier_painter" cargo build --release -q -p easel --target-dir target/painter
boxes=$(awk '/^const BOXES/,/^\];/' crates/paint/src/palette.rs | sed -n 's/^        "\([a-z-]*\)",$/\1/p')
[ -n "$boxes" ] || { echo "build-engine: no boxes found in crates/paint/src/palette.rs (BOXES)" >&2; exit 1; }
rm -rf target/painter/boxes
for box in $boxes; do
  mkdir -p "target/painter/boxes/$box"
  cp target/painter/release/easel "target/painter/boxes/$box/easel"
  echo "painter $box" > "target/painter/boxes/$box/studio"
  echo 4800 > "target/painter/boxes/$box/width"
  "target/painter/boxes/$box/easel" tubes --markdown > "target/painter/boxes/$box/tubes.md"
done
# (grep -q would end the pipe early, and with pipefail a broken pipe reads as "no match": count instead)
check() {
  local b=$1 n
  n=$(strings "$b" | grep -c -e "$HOME" -e "/Users/" || true)
  if [ "$n" != 0 ]; then
    echo "build-engine: $b still names a local path ($n strings):" >&2
    strings "$b" | grep -o -e ".\{0,30\}/Users/[^ ]\{0,40\}" | head -3 >&2
    return 1
  fi
}
# the artist's easels must hold no local path at all (ENG-7)
for box in $boxes; do check "target/painter/boxes/$box/easel"; done
# the replay build (operator only, never in a studio) keeps one: env!("CARGO_MANIFEST_DIR"), the default EASEL_ROOT of
# its developer mode, which no path remapping reaches; anything more is an error
n=$(strings target/release/easel | grep -c -e "/Users/" || true)
if [ "$n" -gt 1 ]; then check target/release/easel; fi
shasum -a 256 target/release/easel target/painter/boxes/*/easel
