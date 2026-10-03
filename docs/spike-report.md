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
env: PATH=/usr/bin:/bin HOME USER LANG CLAUDE_CONFIG_DIR=~/.atelier/claude
     CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 DISABLE_AUTOUPDATER=1
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

**The email.** Claude Code adds the account's email as "the user's email" whenever its stored
profile (`.claude.json`, `oauthAccount`) has one. The runner removes email and names from the
atelier's own config before each launch, and the probe then shows an empty session context.
But Claude Code refetches the profile during a session and writes the email back, so the
removal is not trusted: every transcript is audited after every sitting (NFR-9), and a hit stops
the atelier. Recommended for production: log the atelier in with `claude setup-token` (the
documented route for headless use), which may carry no profile at all; to be verified.

## 4. A test painting

(filled in when the capped sitting ends)

## 5. Viewer

claude-paint's studio viewer, with a Claude Code branch in its parser, shows the spike session
live from the transcript: picker ("Untitled, in progress · Claude Opus 5.5 · thinking"),
canvas, code, thinking and journal.

## 6. Terms of use

(see check-in note)

## 7. Observations worth keeping

- **The painter narrates to someone.** Between tool calls the model writes short progress lines
  ("Toning layer is down. Now laying in the sky...") addressed to whoever sent the first message.
  That is an assistant habit, not something we asked for. Under principle 3.9 we don't instruct
  it away; we record it, and it is a candidate for a measured comparison later.
