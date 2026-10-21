# Upstream: claude-paint

Source: https://github.com/aliceisjustplaying/claude-paint (Alice; code MIT,
texts and paintings CC BY 4.0). Gallery: https://stillwet.art.

Merged: `fea9aa62` (2026-10-21; before it `693f49f2`, 2026-10-13, and `78c86ce`, 2026-10-10), on branch `upstream`
(her files, unmodified, at our paths) and merged into `main`. The exact commit is in `tools/upstream/commit`; every
work records it (`engine_upstream` in its manifest). First taken: `a198dd0` (2026-10-03, after tag `round-22.1`).

She rewrote her history on 2026-10-18/19 (the paintings' records and binaries moved out): `a198dd0`, `78c86ce` and
`693f49f2` are no longer on her main; their code is (`693f49f2`'s twin is `0dc2a5eb`, the same files on every mapped
path). Our branch `upstream` still holds what we took from each, and import.sh copies files, so nothing here depends
on her old ids; anything that compares with her history (`git log`, `merge-base`) starts from the twin.

What we take, and where it lives here: `tools/upstream/map.txt`. Not taken: the research notes on individual
painters and motifs (they steer a painter's subject), the pi harness's runner (painter.ts, its prompt and
compaction), her rounds, records, archive and paintings.

In touch: https://github.com/aliceisjustplaying/claude-paint/issues/37 (2026-10-10): the atelier introduced, the
scratch-canvas classifier finding and the borderline rag test reported, and a question whether she'd take the width
as an option (`--@ width`, her default 2400). If she does, "The atelier's changes" below shrink.
2026-10-12, a follow-up there: measured with `runner/startprobe.py`, her `scratch` description stopped 32 of 60 starts,
ours 1 of 60; a small PR with the wording offered. If her description changes, ours goes (server.ts and below) and
the probe runs again on the merged tools.
2026-10-13: https://github.com/aliceisjustplaying/claude-paint/pull/66, the width as an option, from the owner's fork;
merged as #101 (2026-10-15; after her history's rewrite `d68525eb`). Since the sync of 2026-10-21 the width is hers:
a file `width` (4800) beside the painter's easel, written by tools/build-engine.sh and copied by runner/studio.py;
our ATELIER/NEW_WIDTH, WIDTH_MARK and LOOK_SCALE changes are gone.

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
7. `bash tools/upstream/live-check.sh` - a painting made with the newest tools replays byte for byte (a smoke test
   of the new easels). Finished paintings are not repainted on the new engine: each is kept with the easel it was
   painted on (REC-4, NFR-1; the owner, 2026-10-21). `bash tools/upstream/verify.sh` is optional, a report only.
8. `python3 runner/probes.py` - the production setup with the new tools, audited.
9. Merge into `main` between works (a work in progress keeps its own easel, but each sitting loads the painter
   tools from `main`), then the About page if the painters' tools changed, and an atelier event in history.md.

## The atelier's changes (kept on every merge)

- `engine/crates/easel/src/main.rs`: `ATELIER` (on when `tools/build-engine.sh` builds: `ATELIER_BUILD`): the journal
  named `journal`, and a new painting without the paper-and-pastel switch (`--@ paper`: the atelier paints in oil;
  the owner, 2026-10-21). Its help names "the journal" and "the easel guide", not her paths. Off in a plain
  `cargo test`, so her tests hold.
- `engine/crates/easel/src/api.rs`: `CANVAS_HELP` offers no `paper=` in the atelier's build (`crate::ATELIER`).
- `engine/crates/easel/src/session.rs` `root()`: built with `--cfg atelier_painter` (the painter's easel), it leaves out
  her fallback to `CARGO_MANIFEST_DIR`, the one build path no remapping reaches (ENG-7); the cfg is declared in
  `engine/crates/easel/Cargo.toml` (`[lints.rust]`).
- `engine/scripts/check_painting` and `engine/scripts/compare_images.py`: ours, not hers. Since her #166 (b04d78a6)
  her check says "check: ok" when the replay meets an image tolerance (±2 levels a channel), and her compare_images.py
  applies that tolerance on the same platform too. Ours ask for the replay to equal the live canvas byte for byte on
  the same platform (the tolerance only across platforms): REC-4 keeps the verdict as a record of the work (the
  painter's canvas hangs either way since 2026-10-21), so it should say exactly what it found, `EASEL_NO_BUILD=1` uses the replay easel
  already built, and check_painting clears every `PAINT_*` variable first (hers change engine 5's and later output:
  `PAINT_SMALL_TILES`, `PAINT_COARSE_AGING`). On every merge, keep ours. Her tests of hers
  (`engine/scripts/tests/check_painting_test.py`, the image tolerance tests) then fail here: known, see below.
- `tools/build-engine.sh`: no local paths in the binaries (ENG-7); byte-identical builds (her release profile is
  incremental and accepts drift between builds: ours is not); the replay easel, and the painter's easel (one binary
  since her #165) set up per box in `target/painter/boxes/<box>/` with `studio` ("painter <box>"), `width` (4800) and
  `tubes.md`. Nothing in a painter's easel is reachable by the painter (bin/ is hidden), so all boxes in one binary
  is no white-room matter; its replies name only its own box.
- `engine/Cargo.toml`: `[profile.release] incremental = false`, so a plain `cargo build --release` (scripts/replay_easel,
  the scripts' tests) makes a replay easel that paints as the painter's does, not only build-engine.sh's. An
  incremental one left work i-010 unverified (2026-10-18). Test `engine/scripts/tests/release_profile.sh`.
- `materials/easel_guide.md`: the tube table is the every box's (`easel tubes --markdown`; each studio's copy has its
  own box's, runner/studio.py); "close up" for crops; the journal and the log without file paths; two lines
  reworded for the white room ("as dirty as a working palette gets", "as many tiles as one reply holds"); the
  scratch canvas's log without its paths (`log` with `scratch: true`; put aside "with its log"), and a whole view
  "about 21% of a 4800-pixel canvas's width" (hers: 42% of 2400) (2026-10-21); under `size`, what the fixed width
  of 4800 pixels means for a canvas's size: where the weave stops showing (24000 ÷ threads per cm, in mm) and that
  a larger canvas holds the same picture at a larger scale (the owner, 2026-10-21).
- `materials/easel_guide.md`, since fea9aa6 (the owner, 2026-10-21): without paper and pastel (the `paper` canvas
  option, the section "Paper", pastel in "Drawing" with the sheet, the dry brush, the knife over pastel, the puff and
  the tap; the pastel stick held up), without `probe`, `reference`/`reference_list` and look's `edges` mode (not
  served: numbers and a computed map are not a painter's way of looking; the subject is the painter's), and "a mask
  that is already soft" for her "graded". Her section "Color, planes and open coverage" (left out since 693f49f) she
  took out herself (90f9ae48); if it comes back, take it out again.
- `easel-mcp/src/server.ts`: her painter tools over MCP, with the atelier's read/write/edit; the log without its
  box line (a box may be named after a painter); its own survey reply (hers speaks of a budget); `note` without the
  journal's path; a rebuild's progress without the painter's chunk count; no `probe`, `ref`, reference tools,
  `edges` mode or pastel stick (its header says what was last ported).
- `easel-mcp/src/upstream/easel-client.ts`: `tail()`'s default note points to `log` with an offset, not to the
  painting's file. Her chunk waits are taken as they are (`WIDE_WAIT_MS`, 48 and 50 minutes at 4800 px).
- `easel-mcp/src/upstream/journal.ts`: `JOURNAL` is `journal` (hers `notes/journal.md`). server.ts names it so in
  `note`'s reply (`noted in journal`, `revised in journal`), where the easel and journal.ts give its absolute path.
- `tools/upstream/import.sh`: the cache's fetch takes tags she moved (`--force`).

Known, hers: `rag::tests::a_dry_rag_leaves_a_pale_tint_and_spirits_lift_nearly_to_the_ground` failed here at 78c86ce
and 693f49f alike (0.8993 against its 0.9); at fea9aa6 it passes. Her script tests that expect her tolerant
check_painting and compare_images.py (`engine/scripts/test`'s baseline guards) fail on ours, by design (above).

A copy of the repository for a sync (git worktree) needs two local links the clone doesn't carry:
`engine/notes/easel_guide.md -> ../../materials/easel_guide.md` (her tests read the guide there) and
`easel-mcp/node_modules -> ` main's (the packages, when package.json is unchanged). `easel-mcp/test/upstream.ts`
runs after `tools.ts`, in the same studio: it needs the canvas `tools.ts` paints.

## Changes

Engine changes are atelier events (requirements ENG-5), listed here with their date and reason.

- 2026-10-21 after a dead-code audit (the owner): the easel's help and two width errors say what the atelier's
  build does (the journal, the easel guide, the log's width, `NEW_WIDTH`), and `logged_width`'s fallbacks name
  `LEGACY_WIDTH`; the painting engine is unchanged. The painters' tools: `note` answers "noted in journal" /
  "revised in journal", not the journal's absolute path; the easel guide's scratch canvas section gives no file
  paths, and a whole view is about 21% of a 4800-pixel canvas. Checked: the easel's tests, the runner's, the easel
  tools (tools.ts, upstream.ts), the white room, and ii-010 replayed byte for byte with the new replay easel.

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

