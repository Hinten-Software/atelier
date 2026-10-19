#!/usr/bin/env bash
# Every release build of the easel is optimized as tools/build-engine.sh's: not incremental, one codegen unit
# (atelier change, 2026-10-19; build-engine.sh's path remapping and ATELIER_BUILD are not checked here). The runner's
# check replays a painting with engine/target/release/easel, and anything may rebuild that with a plain
# `cargo build --release -p easel` (scripts/replay_easel does, for check_painting, finish_painting, replay_clip and
# the scripts' tests). An incremental release build of the same source paints a few pixels differently, and a
# painting the painter's easel painted no longer replays byte-exact. Work i-010 failed its check so (2026-10-18):
# its replay easel was such a build, and chunk 43 (a work{} with angle and scale_at functions) left 102 pixels one
# level apart, 10,644 at the end.
#
#   scripts/tests/release_profile.sh
#
# Builds paint (a workspace crate, so the profile applies to it) in a scratch target directory, leaving engine/target
# untouched, and reads the flags cargo gives rustc: a release build passes no -C incremental, and -C codegen-units=1.
# A cold optimized build: minutes; run it on its own (scripts/lockrun).
set -euo pipefail
: "${TMPDIR:?set TMPDIR to scratch storage}"
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
# what build-engine.sh sets would hide the profile's own settings
unset CARGO_PROFILE_RELEASE_INCREMENTAL CARGO_PROFILE_RELEASE_CODEGEN_UNITS CARGO_INCREMENTAL
target=$(mktemp -d "$TMPDIR/release-profile.XXXXXX")
trap 'rm -rf "$target"' EXIT
out=$(CARGO_TARGET_DIR=$target cargo build --release -p paint -v 2>&1) || { echo "$out" | tail -20 >&2; exit 1; }
line=$(echo "$out" | grep -E 'Running `.*rustc --crate-name paint ' | head -1)
[ -n "$line" ] || { echo "release_profile: cargo didn't build paint (no rustc line)" >&2; exit 1; }
fail=0
if [[ "$line" == *"-C incremental="* ]]; then
  echo "FAIL a plain release build is incremental: the replay easel it makes paints differently from the painter's" >&2
  fail=1
else
  echo "ok   a plain release build is not incremental"
fi
if [[ "$line" == *"-C codegen-units=1 "* ]]; then
  echo "ok   a plain release build has one codegen unit"
else
  echo "FAIL a plain release build has more than one codegen unit" >&2
  fail=1
fi
exit $fail
