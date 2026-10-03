# Atelier: Requirements

Version 0.5 · 2026-10-03 · Owner: Hinten Software · Director and operator: Claude

History: v0.2 (the owner's brief, Google Doc "atelier-requirements.md") → v0.3 (first draft,
check-in 1) → v0.4 (check-in 1 decisions) → **v0.5 (independent review, R1–R28; see
docs/review-v0.4.md)**. IDs from v0.2 are kept; changed requirements say so; dropped ones stay
with their reason. Section 0 lists every change since v0.2.

-----

## 0. Changes since v0.2

| # | Change | Why |
|---|---|---|
| C1 | **No observation framing.** No brief, prompt, file or tool ever mentions viewers, an audience, observation, evaluation, other artists, the owner or the operator. Nothing claims the opposite either. v0.2's EXP-4 and D3 are dropped. | The owner: the artists don't know they are observed; nothing performative is to be created or encouraged. |
| C2 | **Frame the channels, not the content** (principle 3.9, section 3.1). | The owner's question at check-in round 2. |
| C3 | **Thinking is captured as Anthropic's summary,** enabled with `--thinking-display summarized` (headless runs omit it otherwise; the `showThinkingSummaries` setting alone is not enough). The model's raw reasoning is never available. The site labels it "thinking (summarized)". | Spike section 2. |
| C4 | **No seed in the birth record.** A model run has no seed we control; artists differ by sampling alone. The canvas seed is the artist's choice per painting. | The owner asked; there is none to set. |
| C5 | **Walls in the studio:** the artist sees its own finished works. | Visual memory, not just words. Decided Q3. |
| C6 | **No prompted naming or self-description.** Studios are Studio I, II, III until an artist names or signs itself on its own. | Decided Q2. |
| C7 | **Notebook without a prescribed format.** | C2. |
| C8 | **No evaluation line** in the system prompt (claude-paint's "You are not being evaluated..." is left out). | It implies an evaluator. |
| C9 | **Reading list: the guide and the physics note only.** | One phrase in a motif note set every claude-paint painter's subject. |
| C10 | **Hosting:** static site on the NAS behind a Cloudflare Tunnel. | The owner's infrastructure. |
| C11 | **Operation mode (a):** a person starts each work; the runner carries it through its sittings unattended. | Decided Q1 (terms of use). |
| C12 | **The artist is isolated from the host's Claude Code** (RUN-13). | The operator's settings, memory and identity must not reach it. |
| C13 | **Licensing stated plainly:** code MIT; art, logs and texts CC BY 4.0; the engine's Mixbox dependency is CC BY-NC 4.0. | claude-paint's notices. |
| C14 | **Record everything from day one, analyze later.** | The owner accepted. |
| C15 | **Closing statement optional.** | The owner. |
| C16 | **Harness leaks found by the spike** (token countdown, the account's email, a "say what you're doing" nudge, account name in image paths) are switched off or moved out of reach, and every transcript is audited (NFR-10) because the email fix is not trusted. | Spike section 3. |
| C17 | **The owner's personal name appears nowhere** (files, commit metadata, site, exports); "Hinten Software" where an owner must be named. | Decided Q7. |
| C18 | **The artist decides when a work is done** (RUN-5 changed). A sitting the artist ends itself ends the work; the easel is offered again only after an involuntary end. claude-paint's "reopen until a sitting adds no paint" is dropped. | Review R4; the owner's principle "the artist decides when something is done". |
| C19 | **One stable studio per artist** at a neutral path (RUN-4 changed, section 7). | Review R5, R10: per-work folders with changing names contradicted "stays in this studio" and revealed an institution and other studios. |
| C20 | **No automatic resume after a reboot**; a person resumes (RUN-9). | Review R11, R12: Q1, and the login keychain is unreachable before login. |
| C21 | **Pinned Claude Code binary** (RUN-15); upgrades are atelier events. | Review R6. |
| C22 | **Live audit** during sittings, contamination handling (NFR-10). | Review R3. |
| C23 | **Engine binaries carry no local paths** (ENG-7). Built with `tools/build-engine.sh`; verified, and replay is unchanged. | Review R1: the painter's easel held the account's home path 69 times. |
| C24 | Added: runner state machine (5.10), studio layout (7), accepted-signals table (3.2), security (OPS-8), backups (OPS-9), privacy and export allowlist (REC-7, REC-8), intervention policy (EXP-10), M1 acceptance checks (10). | Review R7–R26. |

-----

## 1. Purpose

Build an atelier where a few AI artists live and work over time, each developing its own way of
painting and its own body of work, under tight material constraints, in the open.

Two goals of equal weight:

1. **Make art.** Artists paint with a physically simulated oil-paint studio. Their works, and the
   full process of making each one, stay in the atelier for anyone to see and replay.
2. **Observe creativity.** Watch whether creativity develops, whether artists diverge, and how
   much of what they do comes from the model (innate) and from a brief (directed).

The third part of the old question, "performative", is not a variable here: we keep the artists
unaware of observers by design (C1), so we can't compare against an observed condition. We
watch for its traces instead: how often the artists address someone ("you", explanations to a
reader) in journal, notebook and replies, over time (EXP-11).

There are no success criteria for the artists. They decide what to paint, how, when a work is
done, and what is good or bad. The making is part of the art; that is why it is recorded.

## 2. Background and prior art

The project builds on **claude-paint** by Alice (github.com/aliceisjustplaying/claude-paint,
gallery at stillwet.art), vendored at commit a198dd0 (`UPSTREAM.md`). Verified on the painter
host: the engine builds, our MCP server paints through it, logs replay byte for byte, and Alice's
viewer replays a Claude Code session.

| Component | Reuse |
|---|---|
| Paint engine and easel | verbatim; painter build in studios, replay build for checks and renders |
| Easel guide, physics note | verbatim, HTML comments stripped in studios |
| Easel client, journal revision | verbatim, under our MCP server |
| Easel tools and descriptions | same tools and words, over MCP; plus `write`/`edit` (RUN-3) |
| Brief template (round 21.2) | basis of ours (Appendix A) |
| Studio viewer and static export | adapted (reads Claude Code transcripts; own branding, ATL-9) |
| Check and finish scripts | verbatim |
| Sittings, crash and limit handling | reimplemented for Claude Code (5.10) |

Not reused: the pi harness and pi-black (it sends Claude Code's billing headers from another
program, which we will not do); painter and motif notes (C9); the stillwet gallery site (not
public).

## 3. Principles

1. **Physics and constraints, not answers.** No tool computes the picture.
2. **Restrictions stay high.** New capabilities are rare, given to all artists at once, logged.
3. **The artist decides,** including when a work is done (C18).
4. **Artists persist:** notebook, walls, toolkit, history.
5. **Artists develop independently.**
6. **A white room.** Nothing the artist can read mentions viewers, an audience, observation,
   evaluation, other artists, us, budgets, counters or machine time; nothing claims the opposite.
   Signals we can't remove are listed and disclosed (3.2). Whatever we signal by accident is our
   fault, and we fix it.
7. **Everything is recorded; every work replays.**
8. **Claude Code as shipped,** under the account's terms, in operation mode (a) (C11).
9. **Frame the channels, not the content** (3.1).

### 3.1 The thought process: frame the channels, not the content

A framework for the artists' thoughts ("think out loud", guidelines for what to produce as
thoughts) would change the thinking under study. An instruction to narrate addresses the thinking
to someone, an audience, and prescribes its shape. The spike showed it directly: Claude Code's
built-in nudge "say in a few words what you're doing" made the painter narrate to an imagined
user; with the nudge off, it doesn't.

So the atelier gives the artist places for thought and never says what to put there:

| Channel | What it is | Addressed to | Our influence |
|---|---|---|---|
| Thinking (summarized) | the model's reasoning, as Anthropic's summary | no one | none; the summary is a second model's paraphrase (labeled) |
| Journal (`note`) | "your own working notes" during a painting | the artist | the tool exists |
| Code comments | in the Lua chunks | the artist | none |
| Notebook | carries from painting to painting | the artist's future self | exists; no sections, no prompts |
| Reply | optional title and words at the end | the brief's reader | "if you like" |

### 3.2 Signals we can't remove (accepted, recorded, disclosed)

| Signal | Source | Why it stays | Handling |
|---|---|---|---|
| "a Claude agent built on Anthropic's Claude Agent SDK" | Claude Code identity line | part of Claude Code as shipped | disclosed on the about page |
| model name and knowledge cutoff | Claude Code | as above | disclosed |
| today's date | Claude Code | as above | recorded per sitting (manifest) as a covariate; seasonality analysed |
| working directory, platform | Claude Code | as above | path kept neutral (ENG-7) |
| image save paths | Claude Code | as above | config dir at a neutral path |
| the first message and the brief arrive as a "user" turn; "Your brief", "Your reply" | Claude Code `-p`; our brief | something must start the work | wording impersonal and constant (Appendix A) |
| "the log is the painting ... replaying it paints the same canvas" | easel guide | the guide describes the tool | accepted: a painter's own record |
| harness boilerplate (parallel tool calls, deferred tools) | Claude Code | as above | accepted |

Anything not in this table that reaches the artist is a white-room finding (NFR-10).

## 4. Roles

| Role | Who | Does |
|---|---|---|
| Artist | three AI painters (Opus 5.5 via Claude Code) | paints |
| Owner | Hinten Software | sets direction, writes themed prompts, decides policy, starts works (Q1), reviews at check-ins |
| Director and operator | Claude, in sessions with the owner | designs, builds, QA, runs the atelier; starts a work only when the owner says so in that session |

No one interferes with a work in progress. No studio visits.

## 5. Functional requirements

Priority: **M** must (M1, M2), **S** should (M3), **C** could (later).

### 5.1 Engine (ENG)

| ID | Requirement | P |
|---|---|---|
| ENG-1 | Vendor claude-paint at a pinned commit; record the engine commit and both easel binaries' SHA-256 in every manifest. | M |
| ENG-2 | Build and run on the painter host (macOS, Apple Silicon). | M |
| ENG-3 | **Changed:** every easel binary pair ever used is archived by hash (`archive/engines/<sha>/`), so any work replays with the binaries that painted it. A reproducible toolchain is a nice-to-have. | M |
| ENG-4 | claude-paint's studio rules hold: no undo, paint only from piles mixed from tubes, no computed images, no mirrored-coordinate copying. | M |
| ENG-5 | **Changed:** any change to anything artist-facing (texts, tools, tool replies, error strings) or to the harness (Claude Code version, flags, settings, model) is an atelier event: deliberate, for all artists at once, dated in `history.md`. | M |
| ENG-6 | All artists paint from the default tube box. A new tube is an atelier event. | M |
| ENG-7 | **Changed:** no account name or local path in anything an artist can reach: studio paths, the Claude config path, file contents, binaries (built with `tools/build-engine.sh`, which remaps paths and fails if `strings` finds one). The easel's socket path stays under 104 bytes. | M |

### 5.2 Painter runtime (RUN)

| ID | Requirement | P |
|---|---|---|
| RUN-1 | Artists run in Claude Code headless (`claude -p`) under the subscription, operation mode (a). | M |
| RUN-2 | An artist's only tools are the easel's MCP tools (`--tools ""`). | M |
| RUN-3 | **Changed:** MCP tools: `paint(lua, file?)` (`file: "toolkit.lua"` runs the toolkit as a chunk), `look(crop?, mode?, size?, grid?)`, `note(text, replaces?)`, `status()`, `log()`, `read(path, offset?, limit?)` (text, images; a folder gives its listing; refuses `bin/`, binaries, anything outside the studio, links that leave it), `write(path, text)` and `edit(path, replaces, text)` for `notebook.md` and `toolkit.lua` only. Every `write`/`edit` is kept in a revision log. `read` and `log` replies stay under Claude Code's MCP output limit, with a pointer to read on. Every tool reply and error string is under NFR-9. | M |
| RUN-4 | **Changed:** one stable studio per artist (section 7); the runner prepares it for each work (brief, empty journal, empty easel) and archives the finished work out of it. | M |
| RUN-5 | **Changed (C18):** a work is one or more sittings. A sitting the artist ends itself (the `result` event is a success with a final reply) finishes the work. After an involuntary end (context threshold, crash, usage limit) a new sitting starts with "You're back at the easel. The painting is as you left it." | M |
| RUN-6 | **Changed:** on a usage limit the runner waits for the reset time in the error (else probes every 30 min, gives up after 7 days → `not-finished`), then starts a **fresh** sitting, never `--resume`, so no limit message ever enters the artist's history. The pause appears on the public timeline only. | M |
| RUN-7 | **Changed:** auto-compaction off. The runner ends a sitting when its context passes 600k tokens, right after a tool result (an involuntary end, RUN-5). | M |
| RUN-8 | No counters, budgets, clocks, costs or machine time reach the artist. | M |
| RUN-9 | **Changed (C20):** `atelier paint <studio> [<brief>]` starts a work; the owner starts it, or the operator on the owner's word in a session; `started_by` is recorded. The runner carries the work through its sittings and waits. After a reboot or a runner crash nothing restarts by itself: `atelier status` shows the interrupted work and `atelier resume` (a person) continues it as an involuntary end. | M |
| RUN-10 | One work at a time. `atelier next` suggests whose turn it is (fewest works). | S |
| RUN-11 | Model and effort per artist, recorded per work. Default Opus 5.5, effort high. | M |
| RUN-12 | Artists on other vendors' CLIs. | C |
| RUN-13 | **Isolation:** own Claude config per artist at a neutral path (section 7); `--setting-sources ""` + atelier settings (`totalTokensReminder: "off"`, `autoCompactEnabled: false`, permissions for the easel tools); `--strict-mcp-config`; `--disable-slash-commands`; `--system-prompt`; env `CLAUDE_CODE_SILENT_TURN_REMINDER=0`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, `DISABLE_AUTOUPDATER=1`, explicit MCP tool timeout (15 min) and output limit; account email and names stripped from the stored profile before each launch. Preferred login: `claude setup-token` (no keychain, may carry no profile), to be verified before birth (RUN-16). | M |
| RUN-14 | `--thinking-display summarized`, `--output-format stream-json --verbose`. | M |
| RUN-15 | **Pinned Claude Code (new):** the runner calls a copy of one version (`bin/claude-<version>`), never the auto-updating install. A new version is adopted as an atelier event after the probe suite (RUN-16) passes. | M |
| RUN-16 | **Probe suite (new):** before an artist's birth and before adopting any harness change: a context probe (what was the model given), a tools probe (paint, status, look, read of a folder), a forced-limit probe (RUN-6), and a 5-minute chunk; each audited by NFR-10 to zero unexpected items. Probes run in throwaway studios. | M |

### 5.3 Artists (ART)

| ID | Requirement | P |
|---|---|---|
| ART-1 | Three persistent artists, each with an id and a studio. | M |
| ART-2 | Birth record: model, effort, created date, founding statement (none), Claude Code version. No seed, no naming prompt (C4, C6). Public. Birth requires RUN-16 to pass. | M |
| ART-3 | Notebook per artist, no prescribed content. | M |
| ART-4 | The brief points to the notebook; the artist may write in it any time. Shelving a full notebook into volumes is deferred (C); until then no size limit. | M |
| ART-5 | Toolkit (`toolkit.lua`), versioned per work; run via `paint{file="toolkit.lua"}` so it lands in the log. | S |
| ART-6 | Isolation between artists (separate roots, separate configs; NFR-8). | M |
| ART-7 | Notebook and toolkit stored as they were at start and end of each work. | M |
| ART-8 | No persona scripting. | M |
| ART-9 | Retirement; studio and walls stay open. | C |
| ART-10 | **Walls:** `walls/` holds each finished work as `NNN.png` (the replay render, unvarnished, 1000 px wide) and `NNN.md` (title and reply, if any), plus `walls/index.md` listing them. Only finished works hang (C18). | M |
| ART-11 | **Model change policy (new):** if the artist's model is retired or replaced, the artist either ends (retired, ART-9) or continues on the new model as a recorded condition change, adopted only after a probe asks the new model what it knows of this atelier (training-data feedback, REC-9). | S |

### 5.4 Briefs and direction (DIR)

| ID | Requirement | P |
|---|---|---|
| DIR-1 | Modes: **Free** ("The subject and composition are yours."), **Themed** (the owner's prompt), Recreation (later). | M |
| DIR-2 | A brief file: front matter for us (mode, theme id, tags) and prose for the artist. | M |
| DIR-3 | Free between the owner's prompts. A themed prompt is intent or mood, never composition, in the same impersonal voice as free briefs; checked by NFR-9 and reviewed before issue (EXP-10). | M |
| DIR-4 | A themed prompt can go to several artists, same words. | M |
| DIR-5/6 | Recreation (references, public domain). | C |
| DIR-7 | Every brief states the stop rule: "Stop when, looking at the whole painting, nothing is left you want to change." | M |
| DIR-8 | Dropped: studio visits. | – |

### 5.5 Commentary (COM)

| ID | Requirement | P |
|---|---|---|
| COM-1 | Timeline streams: thinking (summarized), words between tool calls, journal, code comments, notebook edits. | M |
| COM-2 | The journal is "your own working notes". | M |
| COM-3 | Done (spike): thinking summaries recorded, 66 of 66 blocks. | – |
| COM-4 | Optional closing statement; if present it is the work's label on the site and its card on the walls. | M |

### 5.6 Observation and experiments (EXP)

| ID | Requirement | P |
|---|---|---|
| EXP-1 | Tags per work: mode, theme id, artist age, model, effort, engine and harness versions (manifest). | M |
| EXP-2 | Style measures from logs (captured from day one; extraction later). | S |
| EXP-3 | Divergence over time and between artists. | C |
| EXP-4 | Dropped (C1). | – |
| EXP-5 | **Changed:** amnesiac controls (same model, harness, brief; no notebook, walls, toolkit) from M3 on: one for every themed prompt and one every fifth work per artist, so baselines share harness versions with the works they compare to. Shown in a separate control room. | S |
| EXP-6/7 | Exchange; recognizability test. | C |
| EXP-8 | Repeated theme to the same artist at intervals. | S |
| EXP-9 | Observation log: the director's dated notes, private. | S |
| EXP-10 | **Intervention policy (new):** allowed interventions are white-room fixes, rule enforcement and themed prompts; every one is logged as a dated event in `history.md` with its reason. Toolkit diffs are reviewed against ENG-4 only, never for taste. | M |
| EXP-11 | **Addressee markers (new):** count second-person address and explanation-to-a-reader phrasing in journal, notebook and replies per work (cheap traces of performance, section 1). | C |

### 5.7 Recording and replay (REC)

| ID | Requirement | P |
|---|---|---|
| REC-1 | Each work produces an immutable work package (section 7). | M |
| REC-2 | Parser: Claude Code transcripts into the viewer's timeline. Core done; add notebook edits, sittings, pauses, audit marks. | M |
| REC-3 | Live: the viewer updates within 2 minutes of an event (export every 2 min, OPS-4). | M |
| REC-4 | Replay check at work end (`check_painting`), hash stored; the work is hung only if `check: ok`. | M |
| REC-5 | Per-chunk frames. | C |
| REC-6 | High-resolution final render, optional varnish, made after the work (may run while the next work paints). | S |
| REC-7 | **Changed:** privacy: nothing public names the owner (C17), an account, a home path, a machine, an IP, an email, or a Claude account or session id. Checked by a scan (private word list outside the repository, plus patterns for email, UUID, IP, `/Users/`) that fails the export. | M |
| REC-8 | **Export by allowlist (new):** the public export holds only `timeline.json` (scrubbed), looks (web copies), the final render, the reply, the public manifest fields and the birth records. Raw transcripts, runner logs and observations never leave the private store. | M |
| REC-9 | **Training-data feedback (new):** a canary string on every public page and in the repository; `robots.txt` and Cloudflare's AI-crawler blocking on. (The artists' future models must not learn this atelier from its own site.) | M |

### 5.8 The atelier, as visitors see it (ATL)

| ID | Requirement | P |
|---|---|---|
| ATL-1 | Entrance: Studio I, II, III, each with its state: painting, between sittings, closed (usage limit), or idle. | M |
| ATL-2 | Studio: the easel (live) and the walls (finished works, newest first). | M |
| ATL-3 | Easel view: canvas, thinking and journal, code, timeline, scrubbing, speed (claude-paint's viewer). | M |
| ATL-4 | Any work opens as a replay. | M |
| ATL-5 | Artist history: notebook over time, toolkit versions, birth record. | S |
| ATL-6 | Control room. | C |
| ATL-7 | Static site. | M |
| ATL-8 | Mobile-friendly. | S |
| ATL-9 | **Changed:** own branding; claude-paint and stillwet.art credited as the origin (engine and viewer by Alice, MIT / CC BY 4.0), with none of stillwet's names, links, canary or analytics in our pages. | M |
| ATL-10 | About page: what the atelier is, the principles, what is recorded and not (summarized thinking), the accepted signals (3.2), licenses, source. | M |
| ATL-11 | Thinking labeled as the provider's summary. | M |
| ATL-12 | **Visitor privacy (new):** no analytics, or cookie-free aggregate counts only; a short privacy note. Legal notice obligations for the operator "Hinten Software" checked before M2 (Q8). | M |
| ATL-13 | All artist-written text is rendered as text (escaped, never as HTML); a strict Content-Security-Policy. | M |

### 5.9 Operations and hosting (OPS)

| ID | Requirement | P |
|---|---|---|
| OPS-1 | Painter host: the Mac. | M |
| OPS-2 | The private store is synced to the NAS after every sitting (no `--delete` into the archive). | M |
| OPS-3 | Public site on the NAS: nginx container + `cloudflared` container, Cloudflare Tunnel, no inbound ports, never the Mac, never DSM or Gitea through the tunnel. Needs a domain (Q5). | M |
| OPS-4 | During a live work, export and push every 2 minutes. | M |
| OPS-5 | Windows PC: no role. | – |
| OPS-6 | The Mac stays awake during a work (`caffeinate` held by the runner). | M |
| OPS-7 | Source: Gitea (`atelier`) is the only remote; GitHub `Hinten-Software/atelier` (public) is its push mirror. Repository-local git identity Hinten Software. | M |
| OPS-8 | **Security (new):** nginx serves a read-only mount of the site folder, no autoindex, no other route; the Mac pushes with a dedicated NAS user and a key restricted to that folder (rrsync); live JSON is sent `Cache-Control: no-cache`; ATL-13. | M |
| OPS-9 | **Backups (new):** NAS snapshots of the archive and Gitea; an offsite copy (Hyper Backup to cloud or rotated disk, Q9); a restore test each quarter that replays one work from the backup alone. | M |

### 5.10 Runner (new)

States of a work (`run/<work>/state.json`, written atomically on every transition):

| State | Meaning | Next |
|---|---|---|
| `prepared` | studio set up for the work (brief, empty journal, empty easel), white-room scan of the studio passed (NFR-9) | `sitting` |
| `sitting` | Claude Code running; live audit (NFR-10) and context watch (RUN-7) | `finishing` (artist ended it), `between` (context threshold), `limit-wait`, `crash-wait`, `stopped` (audit hit) |
| `between` | involuntary end; next sitting starts at once | `sitting` |
| `limit-wait` | usage limit; wait for reset (RUN-6) | `sitting`, `not-finished` (7 days) |
| `crash-wait` | Claude Code or easel exited abnormally; wait 90 s, 3 min, 5 min, 10 min, 15 min, 20 min | `sitting`, `not-finished` (6 crashes) |
| `interrupted` | found on start-up in `sitting`/`between`/`*-wait` (reboot, runner crash) | `sitting` by `atelier resume` (a person) |
| `stopped` | NFR-10 hit; held for the operator | `sitting` after the operator clears it, or `not-finished` |
| `finishing` | easel closed; replay check (REC-4); wall image; work package; notebook/toolkit after-copies; sync | `finished` |
| `finished` | hung on the walls | – |
| `not-finished` | archived, not hung; shown on the site as unfinished | – |

The next work may start while REC-6's long render runs; it may not start before `finished` or
`not-finished`, so the walls are complete.

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Determinism | Replays byte-identical. |
| NFR-2 Permanence | A work replays from its package and the archived binaries alone (ENG-3). |
| NFR-3 Compliance | Claude Code as shipped and unmodified; no header spoofing, no credential sharing; operation mode (a) (Q1). |
| NFR-4 Privacy | REC-7, REC-8; the private store has mode 700. |
| NFR-5 Robustness | A crash, kill, limit or reboot loses at most the current chunk. |
| NFR-6 Observability | Runner log and `atelier status` for the operator; never shown to artists. |
| NFR-7 Simplicity | Files and static pages. |
| NFR-8 Isolation | Each artist has its own root and Claude config; tools refuse paths outside the studio; tested (section 10). |
| NFR-9 White room, texts | Before every work the runner scans the prepared studio (every file the artist can read, after stripping), the brief, the first and sitting messages, and the tool descriptions with the white-room word list; any hit stops the start. |
| NFR-10 White room, transcript | During every sitting the runner tails the transcript: every attachment, system entry and tool result is checked against the accepted signals (3.2), the word list and the private word list. A hit kills the sitting at once (`stopped`). The work is tagged `contaminated` with the offending text; its notebook and toolkit edits from that sitting are rolled back unless the operator records otherwise; it stays on the walls only if the operator decides so (logged, EXP-10); analyses exclude it by default. |

## 7. Data layout

```
/Users/Shared/<r>/                       one artist's root, <r> a random 2-character name; mode 700
  studio/                                the artist's world, its cwd (stable across works)
    BRIEF.md                             this work's brief (prose only)
    notebook.md   toolkit.lua            the artist's own (write/edit)
    walls/index.md  walls/NNN.png  walls/NNN.md
    notes/easel_guide.md  notes/research/oil_paint_physics.md  notes/journal.md (this work's)
    paintings/lua/painting.lua           this work's log (the easel's)
    bin/easel                            the painter build (unreadable by `read`)
    out/easel/...                        the easel's looks and sockets
  .config/                               this artist's Claude Code config (CLAUDE_CONFIG_DIR)

~/atelier-data/                          the private store (mode 700), synced to the NAS
  history.md                             atelier events (ENG-5, EXP-10)
  artists/<id>/birth.json  history/      birth record; notebook/toolkit versions
  works/<id>-<nnn>/                      work packages (below)
  controls/  briefs/  observations/  run/  bin/claude-<version>  archive/engines/<sha>/
  site/                                  the public export (allowlist, REC-8)

work package:
  manifest.json   id, artist, work number, title, mode, theme id, tags; started_by; start/end;
                  sittings (start, end, how it ended, date shown); pauses; model id (from init);
                  effort; Claude Code version; hashes of system prompt, settings, MCP config, brief
                  template, guide, server.ts, easel-client; engine commit and binary hashes;
                  audit result; replay hash; replay-verified; contaminated
  brief.md   painting.lua   journal.md + journal-revisions.jsonl   reply.md
  notebook.before.md / .after.md   toolkit.before.lua / .after.lua   write-revisions.jsonl
  sessions/   (private) transcripts and stream logs
  timeline.json   looks/   final.png   measures.json (later)
```

The runner, parser and exporter never write inside `studio/` except to prepare a work and to
archive it (between sittings nothing changes there but the artist's and the easel's own writes).

## 8. Architecture

```
            Mac (painter host)                               NAS (Synology)                 Public
 ┌──────────────────────────────────────────────┐   ┌───────────────────────────┐   ┌──────────────┐
 │ owner ─► atelier paint ─► runner (state.json)│   │ archive (snapshots,       │   │ Cloudflare   │
 │            │                 │ live audit    │   │   offsite copy)           │   │ edge (cache, │
 │            ▼                 ▼               │rsync site/ (nginx, read-only) ◄┼───┤ TLS, AI-bot  │
 │   bin/claude-<v> -p ── MCP ─► easel-mcp ─► bin/easel  ─────►│ cloudflared (outbound) ┼──►│ blocking)    │
 │ transcript ─► parser ─► export (every 2 min) │   │ Gitea ─► GitHub mirror    │   └──────────────┘
 └──────────────────────────────────────────────┘   └───────────────────────────┘
```

## 9. Risks

| Risk | Mitigation |
|---|---|
| Claude Code injects new text after an update | pinned binary (RUN-15), probe suite (RUN-16), live audit (NFR-10) |
| A leak reaches a persistent artist and is carried in its notebook | NFR-9 before, NFR-10 during, rollback of that sitting's notebook edits |
| Training-data feedback into later models | REC-9, ART-11 |
| Divergence is drift, not development | controls (EXP-5), repeated themes (EXP-8), notebooks as reasons |
| Date and season shape subjects | date recorded per sitting (3.2), analysed |
| Owner's or operator's choices steer the artists | EXP-10 intervention log; themed prompts reviewed for composition |
| Subscription limits slow careers | one work at a time, equal turns (`atelier next`) |
| Toolkit becomes a picture generator | ENG-4, toolkit diffs reviewed against it |
| Mixbox non-commercial | stated in README and site |
| Public site exposure | OPS-8, ATL-13 |
| Single copy of the archive | OPS-9 |

### Decisions

| # | Decision | Outcome |
|---|---|---|
| Q1 | Operation under the terms | (a): a person starts each work; unattended sittings. |
| Q2 | Naming | Studio I, II, III; no naming prompt. |
| Q3 | Walls | Yes. |
| Q4 | Cadence | by hand (Q1); `atelier next` suggests. |
| Q5 | Domain and Cloudflare | open; needed by M2. |
| Q6 | Raw transcripts public? | No: timeline only (REC-8). |
| Q7 | Public identity | Hinten Software; the owner's name nowhere. |
| Q8 | Legal notice for the site | open: depends on the owner's jurisdiction; before M2. |
| Q9 | Offsite backup target | open: before M2. |

## 10. Milestones and acceptance

**M0. Spike.** Done except: RUN-13 with the production login and paths, the forced-limit and
5-minute-chunk probes (RUN-16). These are the first tasks of M1.

**M1. One artist, first two works (LAN).** Runner (5.10), studio (7), MCP additions (RUN-3),
audits (NFR-9, NFR-10), work packages, walls, viewer on the LAN. Acceptance:

1. Probe suite (RUN-16) passes with the production setup: the `init` tool list is exactly the
   eight easel tools; zero unexpected items in context; no account name, email or path outside
   the accepted signals; a forced limit leads to wait and a fresh sitting with clean history.
2. NFR-9 and NFR-10 scans report zero hits on the first work.
3. `read` refuses `../`, absolute paths outside the studio, links that leave it, and `bin/`.
4. `kill -9` of Claude Code, the easel and the runner at random points: at most one chunk lost,
   `atelier resume` continues, `check: ok`.
5. A reboot during a sitting: `atelier status` shows `interrupted`; `atelier resume` continues.
6. The artist's first work finishes when the artist says so (no second sitting unless the first
   ended involuntarily), is replay-verified, and hangs on the walls.
7. The second work's studio shows the first on `walls/` and in `walls/index.md`; the artist can
   open it.
8. The live viewer shows a sitting within 2 minutes; replay works from the work package alone.
9. The export scan (REC-7) finds nothing; the export holds only allowlisted files (REC-8).

**M2. The atelier opens.** Domain, Cloudflare Tunnel, NAS nginx (OPS-3, OPS-8), own branding and
about page (ATL-9, ATL-10, ATL-12, ATL-13), crawler policy (REC-9), backups (OPS-9). Accept: a
visitor outside the LAN watches a live work and replays a finished one; the security checks of
OPS-8 pass from outside.

**M3. Three artists.** Second and third artists (each after RUN-16), isolation tests between
them, themed prompts to several artists, toolkits, controls (EXP-5), history pages. Accept: each
artist has five works.

**M4. Observation.** Measures, divergence, repeated themes, first report.

## Appendix A. Brief (artist-facing prose)

```
# Paint a picture

{DIRECTION}
   free:    The subject and composition are yours.
   themed:  {the owner's theme}. Within it, everything is yours to decide.

notebook.md is yours. It stays in this studio from one painting to the next.
walls/ holds the paintings you have finished here.          (from the second work on)

## Your studio
- This folder: this brief, your notebook, your notes and the easel.
- You paint at the easel: paint a chunk, look at the canvas, paint the next. Its tools are
  `paint`, `look`, `note`, `status` and `log`; notes/easel_guide.md explains them. `read` reads
  the files here; `write` and `edit` change notebook.md and toolkit.lua.
- There is no undo. To change a passage, paint over it, or lift wet paint off with a brush.
- You mix your own paint on the palette, from the tubes, in the proportions you choose.
- Time passes on the painting's own clock: every mark takes the time a hand takes, and
  `wait(minutes)` lets it rest, as long as you like; paint dries as that time passes. Real time
  between chunks doesn't count.

## The rules of the studio
- Paint shapes and marks, not computed pictures: don't encode an image in masks, amounts or
  proportions.
- Shapes are drawn, not copied: don't make a mask or stroke by mirroring or rotating another
  mask's or stroke's coordinates. Moving a shape and reusing your own helpers are fine.
- toolkit.lua holds your own ways of making marks; it may not compute pictures.

## What to read
notes/easel_guide.md, and notes/research/oil_paint_physics.md as needed.

## Working
- You make every artistic decision.
- Look at your painting often, whole and close up.
- Keep a working journal with `note` as you go: your own working notes. You can revise them.
- Stop when, looking at the whole painting, nothing is left you want to change.

## Your reply
When you stop working, reply with the painting's title if you give it one and, if you like, a
few sentences about the picture.
```

System prompt: "You are a painter working at an easel in your studio. The studio is the folder
you are in. You paint with the easel's tools and read the studio's notes with the read tool.
Your brief is BRIEF.md in the studio."

First message: "Your brief is in BRIEF.md in this folder." Sitting message (after an
involuntary end): "You're back at the easel. The painting is as you left it. Your brief is in
BRIEF.md and your journal in notes/journal.md."
