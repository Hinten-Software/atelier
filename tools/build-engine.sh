#!/usr/bin/env bash
# Build both easels with no account name or local path inside them (requirements ENG-7):
# rustc's panic locations and the Lua C sources' __FILE__ name the build machine's paths otherwise.
#   tools/build-engine.sh        -> engine/target/release/easel (the replay build: every box, the operator's)
#                                   engine/target/painter/boxes/<box>/easel and tubes.md, one painter's easel per box
# A painter's easel holds its studio's box only (upstream's rule: nothing in a studio names another box); the runner
# gives a studio the easel of its work's box, "every" unless the owner names another (runner/config.py BOXES).
# The boxes are the easel's own (its all-boxes feature), so a box upstream adds is built here without a change.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo/engine"
cargo_home=${CARGO_HOME:-$HOME/.cargo}
remap="--remap-path-prefix=$cargo_home=/cargo --remap-path-prefix=$repo=/atelier --remap-path-prefix=$HOME=/home"
export RUSTFLAGS="$remap"
# the atelier's changes to the easel (a new painting at 4800 px, the journal named "journal"): on in what we build,
# off in a plain `cargo test`, so claude-paint's own tests hold unchanged (engine/crates/easel/src/main.rs ATELIER)
export ATELIER_BUILD=1
# byte-identical builds: the painter's easel paints, the replay easel (another build) must paint the same bytes from the
# log (REC-4). claude-paint's release profile is incremental since 2026-10-05 and accepts "bounded" drift between
# builds; ours is not
export CARGO_PROFILE_RELEASE_INCREMENTAL=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
# engine/.cargo/config.toml sets CFLAGS for Lua's fixed hash seed; set here, it must carry that define too
export CFLAGS="-Dluai_makeseed()=0x5eedu -ffile-prefix-map=$cargo_home=/cargo -ffile-prefix-map=$HOME=/home"
cargo build --release -p easel
boxes=$(sed -n 's/^all-boxes = \[\(.*\)\]/\1/p' crates/easel/Cargo.toml | tr -d '" ' | tr ',' '\n' | sed -n 's/^box-//p')
[ -n "$boxes" ] || { echo "build-engine: no boxes found in crates/easel/Cargo.toml (all-boxes)" >&2; exit 1; }
for box in $boxes; do  # one target dir for all: only paint and easel rebuild between boxes
  cargo build --release -q -p easel --no-default-features --features "box-$box" --target-dir target/painter
  mkdir -p "target/painter/boxes/$box"
  cp target/painter/release/easel "target/painter/boxes/$box/easel"
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
