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
for b in target/release/easel target/painter/release/easel; do
  if strings "$b" | grep -q -e "$HOME" -e "/Users/"; then
    echo "build-engine: $b still names a local path:" >&2
    strings "$b" | grep -e "$HOME" -e "/Users/" | head -3 >&2
    exit 1
  fi
  shasum -a 256 "$b"
done
