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

None to the engine yet. Engine changes are atelier events (requirements ENG-5)
and are listed here with their date and reason.
