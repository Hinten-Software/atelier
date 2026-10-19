# Upstream: claude-paint

Source: https://github.com/aliceisjustplaying/claude-paint (Alice; code MIT,
texts and paintings CC BY 4.0). Gallery: https://stillwet.art.

Merged: `693f49f2` (2026-10-13; before it `78c86ce`, 2026-10-10), on branch `upstream` (her files, unmodified,
at our paths) and merged into `main`. The exact commit is in `tools/upstream/commit`; every work records it
(`engine_upstream` in its manifest). First taken: `a198dd0` (2026-10-03, after tag `round-22.1`).

What we take, and where it lives here: `tools/upstream/map.txt`. Not taken: the research notes on individual
painters and motifs (they steer a painter's subject), the pi harness's runner (painter.ts, its prompt and
compaction), her rounds, records, archive and paintings.

In touch: https://github.com/aliceisjustplaying/claude-paint/issues/37 (2026-10-10): the atelier introduced, the
scratch-canvas classifier finding and the borderline rag test reported, and a question whether she'd take the width
as an option (`--@ width`, her default 2400). If she does, "The atelier's changes" below shrink.
2026-10-12, a follow-up there: measured with `runner/startprobe.py`, her `scratch` description stopped 32 of 60 starts,
ours 1 of 60; a small PR with the wording offered. If her description changes, ours goes (server.ts and below) and
the probe runs again on the merged tools.
2026-10-13: https://github.com/aliceisjustplaying/claude-paint/pull/66, the width as an option (`EASEL_WIDTH=4800`, the
`--@ width` head line, the chunk limit and crop scale), from the owner's fork. If she merges it, our ATELIER/NEW_WIDTH,
WIDTH_MARK and LOOK_SCALE changes go, and the painters' easel is started with EASEL_WIDTH=4800 instead.

## Taking a newer claude-paint

She develops actively; this is routine. In a worktree of its own (the runner paints from `main`'s files):

1. `bash tools/upstream/import.sh` - her latest onto the branch `upstream` (one commit, her files only).
2. `git merge upstream` - git keeps our changes (below) and brings hers; resolve only real overlaps, keeping
   each change listed under "The atelier's changes" (and taking hers everywhere else).
3. `bash tools/build-engine.sh` - the replay easel and a painter's easel per box (new boxes come by themselves).
4. Tests: `cd engine && cargo test --release --no-fail-fast -p paint -p easel` (her tests run on her behaviour:
   our changes are on only in our build); `TMPDIR=<scratch> engine/scripts/tests/release_profile.sh` (her release
   profile is incremental: keep ours not); `python3 runner/tests/test_*.py`; in a test studio,
   `node easel-mcp/test/tools.ts <studio>` and `node easel-mcp/test/upstream.ts <studio>`.
5. Her painter tools: compare `easel-mcp/src/upstream/easel-tools.ts` (her current version) with what
   `easel-mcp/src/server.ts` serves, and port what is new (its header says what was last ported).
6. `uv run tools/whiteroom.py` - every new text a painter reads, clean or allowed with a reason.
7. `bash tools/upstream/live-check.sh` - a painting made with the newest tools replays byte for byte: the gate.
   `bash tools/upstream/verify.sh` reports whether the finished paintings still replay (a report: their PNGs hang
   either way, the owner 2026-10-10).
8. `python3 runner/probes.py` - the production setup with the new tools, audited.
9. Merge into `main` between works (a work in progress keeps its own easel, but each sitting loads the painter
   tools from `main`), then the About page if the painters' tools changed, and an atelier event in history.md.

## The atelier's changes (kept on every merge)

- `engine/crates/easel/src/main.rs`: `ATELIER` (on when `tools/build-engine.sh` builds: `ATELIER_BUILD`): a new
  painting at `NEW_WIDTH` 4800 px, the journal named `journal`. Off in a plain `cargo test`, so her tests hold.
- `engine/crates/easel/src/session.rs`: `WIDTH_MARK` (`--@ width 4800` in a log's head), `logged_width`,
  `chunk_limit_for` (the chunk limit scaled with the pixel count); her `width_for` (main.rs) reads it. Test
  `the_log_names_its_width`; `the_guide_shows_the_painters_box` (the guide's table is the every box's).
- `engine/crates/easel/src/look.rs`: a crop is shown at 2.4 px a unit (`LOOK_SCALE`) whatever the canvas's width.
- `engine/scripts/check_painting`: `EASEL_NO_BUILD=1` uses the replay easel already built.
- `tools/build-engine.sh`: no local paths in the binaries (ENG-7); byte-identical builds (her release profile is
  incremental since 2026-10-05 and accepts drift between builds: ours is not); a painter's easel per box.
- `engine/Cargo.toml`: `[profile.release] incremental = false`, so a plain `cargo build --release` (scripts/replay_easel,
  the scripts' tests) makes a replay easel that paints as the painter's does, not only build-engine.sh's. An
  incremental one left work i-010 unverified (2026-10-18). Test `engine/scripts/tests/release_profile.sh`.
- `materials/easel_guide.md`: the tube table is the every box's (`easel tubes --markdown`; each studio's copy has its
  own box's, runner/studio.py); "close up" for crops; the journal and the log without file paths; two lines
  reworded for the white room ("as dirty as a working palette gets", "as many tiles as one reply holds").
- `materials/easel_guide.md`, since 693f49f (the owner, 2026-10-13): without her section "Color, planes and open
  coverage" (warm and cool space, tilted planes, facets, multiple viewpoints: a way of painting, unnamed but
  recognisable, offered to every painter). The guide documents tools; a manner is the painter's to find. On a merge
  that brings the section back or changes it, take it out again.
- `easel-mcp/src/server.ts`: her painter tools over MCP, with the atelier's read/write/edit; the log without its
  box line (a box may be named after a painter); its own survey reply (hers speaks of a budget).
- `easel-mcp/src/upstream/easel-client.ts`: `WAIT_MS` raised for 4800 px (see below).

Known, hers: `rag::tests::a_dry_rag_leaves_a_pale_tint_and_spirits_lift_nearly_to_the_ground` fails here at 78c86ce
and 693f49f alike (0.8993 against its 0.9); the paint crate is hers unchanged.

A copy of the repository for a sync (git worktree) needs two local links the clone doesn't carry:
`engine/notes/easel_guide.md -> ../../materials/easel_guide.md` (her tests read the guide there) and
`easel-mcp/node_modules -> ` main's (the packages, when package.json is unchanged). `easel-mcp/test/upstream.ts`
runs after `tools.ts`, in the same studio: it needs the canvas `tools.ts` paints.

## Changes

Engine changes are atelier events (requirements ENG-5), listed here with their date and reason.

- 2026-10-13 claude-paint 693f49f merged (the owner: "start with the upstream sync"; 158 commits): painter names and
  stray references out of the easel guide, its wording plainer; faster replay (reused buffers, less memory traffic,
  finals from the saved end state), the painting's saved state and final PNGs better guarded; a look's light-mode
  companions renamed with it; the boxes alma-tadema, cezanne, hopper, inness, sargent and tonn. Her watercolor
  studio, her Python easel server and live publishing are hers and not used here. Without her guide section "Color,
  planes and open coverage" (the owner; see "The atelier's changes"). The tools the painters are served are
  unchanged (easel-tools.ts as before), so our scratch-canvas wording stands. Checked: her tests (the known rag test
  aside), ours, the white room, the live check at 4800 px, the easel tools, the probes (the long chunk 1427 s, against
  1607 s before), and i-001 (engine 2) and iii-008 (engine 5) replayed byte for byte. tools/upstream/verify.sh named
  the session two ways; her easel no longer finds a session opened as "painting" under another name, so every save
  failed and was reported as DIFFERS. It now uses one name, says FAIL when a save fails, and replays one painting at
  a time (each takes the machine's cores for 10-15 minutes at 4800 px).

- 2026-10-10 claude-paint 78c86ce merged (the owner: "the new tools and verbs, and the new tube boxes"): engines 3-5
  (slower drying with each tube's own rate, the rag, thinner and turpentine, raw linen, impasto that holds its
  relief and clumping hairs, knife tears, the palette board), brushwork (part loads, streaks, gestures, sized
  marks), looks (raking light, gallery light, survey, compare, hold), the scratch canvas, the boxes friedrich,
  giverny, impressionist and seurat. New paintings are engine 5. A work may be given a box (`atelier paint --box`);
  every is the default. Our hand port of the every box (2026-10-07) gave way to hers. The vendor branch and
  tools/upstream were set up for the syncs to come.

- 2026-10-03 `engine/scripts/check_painting`: with `EASEL_NO_BUILD=1` it uses the replay easel
  already built (by `tools/build-engine.sh`, with no local paths inside) instead of rebuilding it
  with plain `cargo build`. The painting engine itself is unchanged.
- 2026-10-06 painting width (the owner: paintings of a fidelity that holds up close and in print):
  - `crates/easel/src/main.rs`: a new painting is begun at 4800 px (`NEW_WIDTH`, was the fixed
    `LIVE_WIDTH` of 2400); a painting goes on and replays at the width its log names.
  - `crates/easel/src/session.rs`: a log names its width in its head (`--@ width 4800`); a log
    without the line was painted at 2400 (`LEGACY_WIDTH`) and replays at 2400, so every earlier
    painting replays exactly as painted (verified pixel for pixel: i-001, i-002). Test
    `the_log_names_its_width`.
  - `crates/easel/src/look.rs`: a crop is shown at 2.4 px to a canvas unit whatever the canvas's
    width, so the painter's looks (limits, sizes) stay as they were.
  - Measured on i-001 replayed at 4800: the same picture (mean difference 1.3 of 255), finer edges and
    texture, about 3.5 times the compute.
  - `materials/easel_guide.md`: "A crop shows the canvas at its full detail" now reads "close up".
- 2026-10-06 time limits scaled with the width (found by the long probe at 4800 px: a chunk that fit at
  2400 outran the tool's wait): `session.rs` `chunk_limit_for` (10 minutes at 2400, 40 at 4800);
  `easel-mcp/src/upstream/easel-client.ts` `WAIT_MS` (`do` 12 -> 42 minutes, `rebuild` 30 -> 120);
  `runner/config.py` `MCP_TOOL_TIMEOUT` 15 -> 45 minutes.
- 2026-10-07 the every box (the owner: after the default-position test, see docs/operations.md): upstream's
  round-31 box of all 54 tubes (commit c0364ba), ported by hand onto our pin: six tubes added to the catalog
  (strontium yellow, barium yellow, zinc yellow, carmine lake, yellow lake, vine black; two drier constants,
  `CHROMATE` and `ZINC_YELLOW`), feature `box-every` on every tube and in `BOXES`, and the painter's easel
  built for that box alone (`tools/build-engine.sh`), so a new painting takes it without a `box` file and
  logs `--@ box every`; the replay easel keeps every box, so earlier paintings (the default box, no box
  line) replay as painted. Not taken: upstream's later drying numbers for the first fourteen tubes (they
  would change earlier paintings' replays) and `notes/research/every_materials.md` (it names painters).
  `materials/easel_guide.md`: the tube table is the easel's own (`easel tubes --markdown`), 54 rows.

