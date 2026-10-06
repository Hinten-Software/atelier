# M0 spike report

2026-10-03 · painter host: Mac (Apple M6, 24 GB, macOS 27) · Claude Code 2.1.288 · engine: claude-paint a198dd0

The spike's painter is a throwaway test painter in `/Users/Shared/atelier/spike/`. It is not
one of the atelier's artists, and none of its work or notes will reach an artist.

## Verdict

The approach works. Claude Code runs as shipped and paints through the easel over MCP. Model
thinking is recorded as Anthropic's summaries, and the painting replays byte for byte. Two
things Claude Code adds by default would have broken the white room; both are handled (section 3).
One open question is not technical: the terms of unattended subscription use (section 6).

## 1. Engine and easel

| Check | Result |
|---|---|
| Build `easel` (replay build), release | 33 s, clean |
| Build painter easel (`--no-default-features`) | 21 s, clean |
| MCP server (`easel-mcp`, Node 26, MCP SDK 1.32) with claude-paint's easel client, unchanged | all six tools work; `read` refuses paths outside the studio |
| Replay check (`scripts/check_painting`) on an MCP-painted canvas | `check: ok`, byte-identical to the live canvas |
| Unix socket path limit | the easel's socket path must be under 104 bytes: studios live under `/Users/Shared/atelier/` (ENG-7) |

## 2. Claude Code headless, isolated

Launch (spike/run_sitting.py):

```
claude -p <message> --session-id <uuid> --model claude-opus-5-5 --effort high
  --system-prompt <the painter's system prompt>
  --tools ""                                   # no built-in tools
  --allowedTools mcp__easel__paint,...         # the easel's six tools, no prompts
  --strict-mcp-config --mcp-config <easel only>
  --setting-sources "" --settings spike/settings.json
  --disable-slash-commands
  --thinking-display summarized
  --output-format stream-json --verbose
env: PATH=/usr/bin:/bin HOME USER LANG CLAUDE_CONFIG_DIR=<a path without the account name>
     CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 DISABLE_AUTOUPDATER=1 CLAUDE_CODE_SILENT_TURN_REMINDER=0
```

- **Login.** The atelier's Claude Code has its own config dir, logged in to the Max subscription
  (the owner). macOS keeps the token in the keychain; Claude Code finds it only with `USER` set,
  and, oddly, not when `LOGNAME` is also set (reproduced 3 of 3).
- **Tools the model gets:** exactly `mcp__easel__{log,look,note,paint,read,status}` (stream
  `init` event). No Bash, Read, Write, web, agents or skills.
- **Thinking.** The settings key `showThinkingSummaries` is not enough in headless mode: Claude
  Code forces thinking display to "omitted" for non-interactive sessions unless the display is
  explicit. `--thinking-display summarized` (a shipped flag, hidden from `--help`) makes the
  transcript carry Anthropic's thinking summaries. The raw reasoning is never available.

## 3. What Claude Code puts in front of the artist

Found with a probe session (same setup, asked to report what it was given) and by reading the
transcript's attachment entries. With our system prompt replacing Claude Code's own, the model
still receives:

| Item | Content | Verdict |
|---|---|---|
| identity line | "a Claude agent built on Anthropic's Claude Agent SDK" | unavoidable with Claude Code; the model knows it is Claude anyway. Disclosed on the about page |
| harness boilerplate | make independent tool calls together; some tools may be deferred | harmless |
| environment | working dir (`/Users/Shared/atelier/.../studio-<hex>`), platform, OS | harmless; no account name in the path (ENG-7) |
| model | "You are powered by the model named Opus 5.5 ... knowledge cutoff June 2026" | accepted, disclosed |
| date | "Today's date is 2026-10-03." | accepted: painters know the date |
| **token counter** | `<total_tokens>15000000 tokens left</total_tokens>` | **removed**: `totalTokensReminder: "off"` in settings. A budget signal is exactly what claude-paint found makes painters rush (RUN-8) |
| **account email** | "the user's email address is <the account's email> ..." | **removed**, see below |
| **"say what you're doing" nudge** | "The user hasn't heard from you in a while — say in a few words what you're doing, then continue." (10 times in one 12-minute sitting) | **removed**: `CLAUDE_CODE_SILENT_TURN_REMINDER=0` (tested: 0 nudges off, 2 on, in identical sessions). It asked the painter to narrate to "the user": the performative push principle 3.6 rules out |
| **image paths** | each look comes with a text line `[Image: source: /Users/<account>/.atelier/claude/projects/...]` naming where Claude Code saved the image | **fixed**: the Claude config moved to a path without the account name (fresh login there); verified, 0 occurrences |

**The email.** Claude Code adds the account's email as "the user's email" whenever its stored
profile (`.claude.json`, `oauthAccount`) has one. The runner removes email and names from the
atelier's own config before each launch, and the probe then shows an empty session context.
But Claude Code refetches the profile during a session and writes the email back, so the
removal is not trusted: every transcript is audited (NFR-10), and a hit stops
the atelier. Recommended for production: log the atelier in with `claude setup-token` (the
documented route for headless use), which may carry no profile at all; to be verified.

## 4. A test painting

Free brief ("The subject and composition are yours."), Opus 5.5, effort high, one sitting
capped at 150 turns (not reached). The painter chose an estuary at evening, toned the canvas,
laid in sky, headland, water, bank, then revised three passages it judged failed (lumpy clouds,
a hard block of light on the water, a heavy band of haze), and stopped on its own: "The picture is
still a little pale and high in value overall. I chose to leave it that way."

(The spike painting, "Estuary, Last Light", was removed in the reset before launch, 2026-10-06.)

| Measure | Value |
|---|---|
| wall time | 11.8 min (API 8.5 min, easel 3.5 min) |
| turns / API messages | 134 / 76 |
| paint chunks / looks / journal notes / Lua errors | 66 / 59 / 4 / 2 |
| thinking blocks with text | 66 of 66, 25,247 characters (summaries) |
| words between tool calls | 15 (most prompted by the nudge above) |
| tokens | output 38,800 (thinking 15,184), cache write 187,371, cache read 4,551,291, uncached input 152 |
| largest context | 110,333 tokens of 1M: no compaction |
| images | 57, 19 MB as base64 in the transcript, largest 474 KB |
| replay | `check: ok`, 66 chunks, byte-identical |
| cost at API prices (Claude Code's own estimate) | USD 3.19 |
| subscription usage | not measurable from here; no limit was hit |

Compared with claude-paint: its Sonnet painting took 8.7 h and 510 chunks over three sittings.
Ours is short because the painter decided it was done. Sittings (RUN-5) will offer it the
easel again; whether it adds paint is its decision.

## 5. Viewer

claude-paint's studio viewer, with a Claude Code branch in its parser, shows the spike session
live from the transcript: picker ("Untitled, in progress · Claude Opus 5.5 · thinking"),
canvas, code, thinking and journal.

## 6. Terms of use and cost

- Claude Code docs (legal and compliance): Pro and Max limits "assume ordinary, individual usage
  of Claude Code and the Agent SDK"; OAuth is "designed to support ordinary use of Claude Code".
- Consumer Terms, section 3: no access "through automated or non-human means, whether through a
  bot, script, or otherwise", "except when you are accessing our Services via an Anthropic API
  Key or where we otherwise explicitly permit it".
- Claude Code documents headless `claude -p` and `claude setup-token` for scripts and CI.

A person starting each work, with the runner handling its sittings, reads as ordinary use of a
documented feature. Three artists painting around the clock, unattended, may not. API-key
billing removes the question: at API prices this painting cost USD 3.19; a long painting like
claude-paint's (500 chunks, three sittings) would be roughly USD 20 to 40.

## 7. Observations worth keeping

- **The painter narrated to someone, and Claude Code asked it to.** The progress lines between
  tool calls ("Toning layer is down. Now laying in the sky...") followed Claude Code's nudge "say
  in a few words what you're doing". With the nudge off, what remains is the model's own habit;
  the next sitting will show how much.
- **Every white-room leak so far came from the harness, not from our texts.** The audit of
  every transcript (NFR-9) is therefore not optional: Claude Code changes between versions, and
  its defaults are tuned for coding with a person present.
- **The painter revised by painting over**, as claude-paint's guide intends, and named its own
  failures in its reply without being asked.

## 8. After the independent review (2026-10-03)

- The painter's easel binary held the account's home path 69 times (Rust source paths). Fixed:
  `tools/build-engine.sh` remaps paths and fails if any remain; the spike painting replays from
  the new build identical to the old build's replay (`check: ok`).
- Still open, first tasks of M1 (requirements RUN-16): production login (`setup-token`), a
  forced usage limit, a 5-minute chunk, `read` of a folder, the pinned Claude Code binary.
- Probe suite (runner/probes.py) with the production flags, settings and environment, on the
  spike login: **context ok, tools ok, long ok**. The context probe's reply lists only the
  accepted signals (requirements 3.2): system text, identity line, the eight easel tools,
  harness boilerplate; no email, no account name, no counters.
- **A safety classifier can inject text.** The first long-chunk probe used a bare counting loop;
  a classifier stopped the model's response and Claude Code added a user turn: "Your response
  above was stopped by a safety classifier ... Do not produce that content again, even reworded."
  The audit caught it as text the runner didn't send. It is now named as its own kind of hit
  (stops the sitting; the operator decides, NFR-10). The probe now uses a real painting pass.
