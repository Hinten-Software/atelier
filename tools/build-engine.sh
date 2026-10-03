#!/usr/bin/env bash
# Build both easels with no account name or local path inside them (requirements ENG-7):
# rustc's panic locations and the Lua C sources' __FILE__ name the build machine's paths otherwise.
#   tools/build-engine.sh        -> engine/target/release/easel (replay build), engine/target/painter/release/easel
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo/engine"
cargo_home=${CARGO_HOME:-$HOME/.cargo}
remap="--remap-path-prefix=$cargo_home=/cargo --remap-path-prefix=$repo=/atelier --remap-path-prefix=$HOME=/home"
export RUSTFLAGS="$remap"
# engine/.cargo/config.toml sets CFLAGS for Lua's fixed hash seed; set here, it must carry that define too
export CFLAGS="-Dluai_makeseed()=0x5eedu -ffile-prefix-map=$cargo_home=/cargo -ffile-prefix-map=$HOME=/home"
cargo build --release -p easel
cargo build --release -p easel --no-default-features --target-dir target/painter
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
# the artist's easel must hold no local path at all (ENG-7)
check target/painter/release/easel
# the replay build (operator only, never in a studio) keeps one: env!("CARGO_MANIFEST_DIR"), the default EASEL_ROOT of
# its developer mode, which no path remapping reaches; anything more is an error
n=$(strings target/release/easel | grep -c -e "/Users/" || true)
if [ "$n" -gt 1 ]; then check target/release/easel; fi
shasum -a 256 target/release/easel target/painter/release/easel
