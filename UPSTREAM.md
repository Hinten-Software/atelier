# Upstream: claude-paint

Source: https://github.com/aliceisjustplaying/claude-paint (Alice; code MIT,
texts and paintings CC BY 4.0). Gallery: https://stillwet.art.

Pinned commit: `a198dd055964b77882b42925ff949043d5e334e5` (2026-10-03, after tag
`round-22.1`). Taken with `git archive` of that commit, unmodified unless listed
under "Changes" below.

| here | upstream | notes |
|---|---|---|
| `engine/Cargo.toml`, `Cargo.lock`, `.cargo/`, `crates/`, `scripts/` | same paths | the engine, the easel, its build and check scripts |
| `LICENSE-claude-paint` | `LICENSE` | |
| `THIRD_PARTY_NOTICES.md` | `THIRD_PARTY_NOTICES.md` | spectral.js (MIT), Mixbox (CC BY-NC 4.0) |
| `materials/easel_guide.md` | `notes/easel_guide.md` | |
| `materials/research/oil_paint_physics.md` | `notes/research/oil_paint_physics.md` | |
| `viewer/upstream/studio/` | `studio/` | kept verbatim for reference; our viewer is adapted from it |
| `easel-mcp/src/upstream/easel-client.ts`, `journal.ts` | `harness/painter/` | used unchanged by our MCP server |
| `easel-mcp/src/server.ts` | `harness/painter/easel-tools.ts` | same tools and descriptions, served over MCP instead of pi |

Not taken: the research notes on individual painters and motifs (Friedrich,
trees, ...), which steer a painter's subject; the pi harness, which our artists
don't use; her runners, records and paintings.

## Changes

Engine changes are atelier events (requirements ENG-5), listed here with their date and reason.

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
