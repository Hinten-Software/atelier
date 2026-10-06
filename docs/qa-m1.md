# Independent QA of milestone 1, and the response

2026-10-03. QA by a separate Claude agent (read-only on the code; ran the automated tests and its own
reproductions; no paid sessions). 25 findings. All blockers and majors are fixed and covered by tests;
the table says how.

| # | Severity | Finding (short) | Fix | Test |
|---|---|---|---|---|
| Q1 | blocker | `read` reached `out/` and `bin/` by changing case (APFS ignores case): machine times, chunk counters | lower-case comparison on the true path (`realpathSync.native`); dot-files anywhere hidden | easel-mcp/test/tools.ts (6 case variants) |
| Q2 | major | `read paintings/lua/painting.lua` showed chunk numbers | served through `logReply` | tools.ts |
| Q3 | major | `paint` replies unbounded; Claude Code's oversize notice uncaught | reply capped (its end kept); any text not sent by the easel is a hit | tools.ts; test_runner "injected" |
| Q4 | major | the audit flagged the artist's own words ("compact") | harness word list removed from tool results; replaced by exact reply matching | test_runner |
| Q5 | major | the artist's titles ("The Watchtower") blocked later works at NFR-9 | the walls index and cards are the artist's: private words only; an NFR-9 failure leaves no work behind | test_runner |
| Q6 | major | the live audit could die silently, skip lines, or never see a transcript | fails closed: unreadable lines are hits, every line checked, missing transcript is a hit, watcher errors stop the sitting | test_runner |
| Q7 | major | unknown attachment kinds without text passed; tool results only pattern-checked | every unknown kind is a hit; attachments' payloads scanned; tool results must equal the easel's logged replies (verified on real Claude Code: tools and context probes pass) | probes; test_runner |
| Q8 | major | resuming a failed `finishing` started a new sitting | `resume` keeps `finishing`; `finish()` is safe to repeat; `finished` written last | test_runner |
| Q9 | major | `kill -9` of the runner left Claude Code running; resume started a second session | the sitting's process group is recorded; `resume` stops it first | test_runner (real kill) |
| Q10 | major | limit timing: `limit_since` never cleared; just-past reset times waited a day or a week; 429 counted as a limit | cleared after any other end; up to 2 h past means now; 429 is a crash | test_runner |
| Q11 | major | probe roots could collide with an artist's root and delete it | `probe<12 hex>`, refused if it exists | – |
| Q12 | major | finishing rebuilt the replay easel without path remapping | `check_painting` with `EASEL_NO_BUILD=1` (UPSTREAM.md) | – |
| Q13 | major | a blocked export left the leak on disk and served it | stage, scan, atomic swap; report outside the site, redacted | runner/tests/test_export.py |
| Q14 | minor | context end checked before a successful finish | finish first | – |
| Q15 | minor | pid reuse after reboot | pid + boot time + command line | – |
| Q16 | minor | dot-files below top level, offset past end, long lines, non-atomic writes | fixed | tools.ts |
| Q17 | minor | "**Note:**" read as a title | labels and colon-endings are never titles | viewer/test_claude_code.py |
| Q18 | minor | a missing private word list switched checks off | the audit refuses to run without it | – |
| Q19 | minor | "as you left it" with no painting; journal not rolled back | first message until something is painted; journal in the rollback | – |
| Q20 | minor | export looser than REC-7/8 | `/Users/` scan, studio path written as "studio", allowlist enforced, `final.png` published, contaminated read from the manifest too | test_export |
| Q21 | minor | no SIGKILL fallback; fragile `model_seen`; test override honored in production; HOME | SIGKILL after 30 s; JSON parse; override only with ATELIER_TEST=1; HOME is the artist's root with the token login | – |
| Q22 | minor | commit email public | the owner's choice: the commit email stays a project address | – |
| Q23 | minor | the white-room check missed the runner's texts; allow rules too broad | scans runner/texts and the easel client; in code only string literals count | tools/whiteroom.py |
| Q24 | minor | manifest and package gaps; probe pass not tied to the harness | engine commit, repo commit, MCP-config hash, pauses; engines archived by hash; `timeline.json` and `looks/` in every package; probe pass keyed to a harness fingerprint | test_runner |
| Q25 | minor | test gaps; shared test folder | per-run folders; export, viewer and kill tests added | – |
