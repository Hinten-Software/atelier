# How it works

Each painter is Claude (Anthropic), run headless through Claude Code with a fixed
system prompt and exactly eight tools: `paint`, `look`, `note`, `status`, `log`, `read`,
`write`, `edit`. The studio is a folder that names things as a painter would: brief,
notebook, toolkit, journal, easel guide, notes on oil paint, walls. A runner prepares
each work, starts and resumes sittings, audits every transcript live for anything from
outside the studio, verifies that the finished painting replays exactly, and hangs it.
The public site is a static export, scanned for private strings before it is
published, served from a NAS through a Cloudflare Tunnel.

| folder | what it is |
|---|---|
| `engine/` | the paint engine and easel (Rust), from claude-paint, with our changes listed in `UPSTREAM.md` |
| `materials/` | what a painter reads in the studio: the easel guide and the notes on oil paint |
| `easel-mcp/` | the easel served to Claude Code as an MCP server, and the studio's file tools |
| `runner/` | the atelier: artists, works, sittings, audits, budget, export, sync and backup |
| `viewer/` | the live and replay viewer (from claude-paint's studio viewer) |
| `site/` | the atelier's own pages |
| `deploy/` | the NAS (nginx and the tunnel) and the visitor notes (a Cloudflare Worker) |
| `tools/` | the engine build, the white-room scan, the token saver |
| `docs/` | requirements, operations, reviews |

`operations.md` describes running it; `requirements.md` describes why each part is the
way it is; `../UPSTREAM.md` what was taken from claude-paint and changed since.
