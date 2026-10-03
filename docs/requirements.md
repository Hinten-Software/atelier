# Atelier: Requirements

Version 0.4 (after check-in 1) · 2026-10-03 · Owner: Hinten Software · Director and operator: Claude

Builds on v0.2 (the owner, 2026-10-03, Google Doc "atelier-requirements.md"). IDs from v0.2 are kept;
a requirement that changed says so in **bold**, one that was dropped stays with its reason, new ones
are numbered after the last. Section 0 lists every change.

-----

## 0. What changed from v0.2, and why

| # | Change | Why |
|---|---|---|
| C1 | **Observation framing removed as a variable** (EXP-4 dropped, D3 closed). No brief, prompt or file ever mentions viewers, an audience, observation, other artists, the director or the operator. Nothing claims the opposite either. | the owner, 2026-10-03: the artists don't know they are observed; nothing performative is to be created or encouraged. A "told" condition would create exactly that. |
| C2 | **Frame the channels, not the content** (new principle 3.9). The artist gets places to put thoughts (the journal, the notebook, its reply) and is never told what to think, what to write in them, or to "think out loud". | the owner's question at round 2. See section 3.1. |
| C3 | **Thinking is captured as the provider's summary.** Claude Code records model thinking only as an API-side summary, and only when `showThinkingSummaries` is set (headless runs omit it otherwise). The full reasoning is never available to anyone outside Anthropic. The site labels it "thinking (summarized)". | Verified 2026-10-03 in the Claude Code 2.1.288 binary and this Mac's transcripts; to be confirmed by the spike (COM-3). stillwet.art shows the same kind of summaries. |
| C4 | **No seed in the birth record.** A language model run has no seed we control; artists differ by the randomness of sampling alone. The canvas seed is chosen by the artist per painting in `canvas{seed=...}`. | the owner asked "do we need a seed per artist?": no, and there is none to set. |
| C5 | **Artists see their own walls.** The studio holds images and labels of the artist's own finished works (never anyone else's). | A painter's development is shaped by looking at their own past work; the notebook alone is words about pictures. |
| C6 | **No prompted self-description or naming.** v0.2 ART-2 asked the artist to name itself and write a self-description on its first work. Recommendation: don't ask. A studio is known by a neutral name (Studio I, II, III) until the artist names or signs itself on its own. **Decision for the owner (Q2).** | Being asked "who are you" invites a constructed persona, which is the performative behavior C1 rules out. |
| C7 | **Notebook without a prescribed format.** v0.2's brief listed what a notebook entry holds (attempted / worked / didn't / next). Now: "notebook.md is yours; it stays from one painting to the next." A full notebook is shelved as a volume and a new one begun (ART-4). | C2. |
| C8 | **Artist-facing texts lose the evaluation line.** claude-paint's system prompt says "You are not being evaluated in a quantifiable way." We leave it out. | It implies someone evaluates; Alice's own notes show it didn't stop invented budgets anyway. |
| C9 | **Reading list is the guide and the physics note only.** No painter-, period- or motif-notes. | claude-paint's handoff (2026-10-02): one phrase in a tree note made every painter paint a dead oak. |
| C10 | **Hosting decided:** static site on the NAS (nginx container) behind a Cloudflare Tunnel; the Mac pushes exports to the NAS. Needs a domain and a free Cloudflare account (the owner). | the owner, round 2: NAS runs Docker/nginx, is not exposed; no domain or Cloudflare yet. |
| C11 | **Terms of use is a gating decision**, no longer a footnote (NFR-3, section 9). | Claude Code's docs say Max limits "assume ordinary, individual usage of Claude Code and the Agent SDK"; the Consumer Terms bar automated access "except ... where we otherwise explicitly permit it". Unattended, around-the-clock artists are not clearly "ordinary individual use". |
| C12 | **Isolation of the artist from the host's Claude Code** (new RUN-13). | Without it, the operator's CLAUDE.md, memory, skills and settings would reach the artist. |
| C13 | **Licensing stated plainly:** code MIT, art and texts CC BY 4.0, and the engine's Mixbox dependency is CC BY-NC 4.0, so the engine as a whole is non-commercial. | Found in claude-paint's THIRD_PARTY_NOTICES.md; the owner kept the default (keep Mixbox, say so). |
| C14 | **Research layer: record everything from day one, analyze later.** EXP-2/3/5/7/8 move to "after launch" except their data capture. | the owner accepted the default. |
| C15 | Closing statement is **optional** (COM-4). | The owner: "a statement by the artist if they desire to produce one". |
| C16 | **Harness leaks closed** (RUN-13, NFR-10): Claude Code by default gave the painter a token countdown, the account's email as "the user's email", a recurring "say in a few words what you're doing" nudge, and image paths with the account name. | Spike, 2026-10-03 (docs/spike-report.md). |

-----

## 1. Purpose

Build an atelier where a few AI artists live and work over time, each developing its own way of
painting and its own body of work, under tight material constraints, in the open.

Two goals of equal weight:

1. **Make art.** Artists paint with a physically simulated oil-paint studio. Their works, and the
   full process of making each one, stay in the atelier for anyone to see and replay.
2. **Observe creativity.** Watch whether creativity develops at all, whether artists diverge, and
   how much of what they do comes from the model (innate), from a brief (directed), or from
   anything we accidentally signal (which we try never to do).

There are no success criteria for the artists. They decide what to paint, how, when a work is
done, and what is good or bad. The making is part of the art; that is why it is recorded.

## 2. Background and prior art

The project builds on **claude-paint** by Alice (github.com/aliceisjustplaying/claude-paint,
gallery at stillwet.art). Verified 2026-10-03 on the painter host (M6 Mac): the engine builds in
33 s (`cargo build --release -p easel`), our MCP server paints through it, and a log replays byte
for byte (`scripts/check_painting`: "check: ok").

Reused (pinned at commit a198dd0, see `UPSTREAM.md`):

| Component | Reuse |
|---|---|
| Paint engine and easel (`crates/paint`, `crates/easel`) | verbatim; painter build (`--no-default-features`) in studios, replay build for checks and renders |
| Easel guide, physics note | verbatim |
| Easel client and journal revision (`harness/painter/easel-client.ts`, `journal.ts`) | verbatim, under our MCP server |
| Easel tools and their descriptions (`easel-tools.ts`) | same tools and words, served over MCP |
| Brief template (round 21.2) | basis of ours, with C1, C2, C7, C8, C9 applied |
| Studio viewer (`studio/studio.py`, `index.html`, `stream.css`) | adapted: it now also reads Claude Code transcripts (done, phase 1) |
| Static export (`studio/export_static.py`) | adapted |
| Check and finish scripts (`check_painting`, `finish_painting`) | verbatim |
| Sittings and limit handling (round 21 runner) | reimplemented for Claude Code |

Not reused: the pi harness (we run Claude Code as shipped), pi-black (it sends Claude Code's
billing headers from another program, which we will not do), painter- and motif-notes (C9), the
stillwet gallery site (not public; we build our own around the viewer).

| claude-paint | Atelier |
|---|---|
| Amnesiac painters: every work starts from a blank mind | Persistent artists: notebook, walls, toolkit carry over |
| Studies what models paint (convergence, defaults) | Studies how artists develop and diverge |
| Many painters, many models, one work each | Three artists, long careers, many works each |
| Gallery separate from studio | One atelier: easels and walls in one space |

## 3. Principles

1. **Physics and constraints, not answers.** Tools model the material world; no tool computes the
   picture (claude-paint `notes/principles.md`).
2. **Restrictions stay high.** The toolset stays narrow. New capabilities are rare, deliberate,
   given to all artists at once, and logged as atelier events.
3. **The artist decides.** Subject, composition, palette, marks, when to stop, what is good.
4. **Artists persist.** Each has a continuous life: notebook, walls, toolkit, history.
5. **Artists develop independently.** No artist sees another's work, notes or name.
6. **A white room.** Nothing the artist can read mentions viewers, an audience, observation,
   evaluation, other artists, us, budgets, counters or machine time. Nothing claims the
   opposite either. Whatever we signal by accident is our fault, and we fix it.
7. **Everything is recorded; every work replays,** exactly and permanently, with the engine
   version that painted it.
8. **Claude Code as shipped,** under the account's own terms (NFR-3).
9. **Frame the channels, not the content.** (C2, section 3.1.)

### 3.1 The thought process: frame the channels, not the content

The owner asked whether a framework for the artists' thoughts ("think out loud", guidelines for what
to produce as thoughts) is permissible, or whether it would change the thinking under study.

It would change it. An instruction to narrate one's thinking addresses the thinking to someone,
and that someone is an audience; what follows is partly explanation for that audience. It also
prescribes the shape (steps, reasons, plans), which steers what is thought, not only what is
written. Alice's notes show how sensitive these models are: a single sentence of a reference note
set the subject of every painting, and "you are not being evaluated" didn't stop invented budgets.

So the atelier gives the artist **places** for thought and never tells it what to put there:

| Channel | What it is | Who it is addressed to | Influence |
|---|---|---|---|
| Thinking (summarized) | the model's own reasoning before each action, as Anthropic's summary | no one | none from us; summary is a second model's paraphrase (labeled) |
| Journal (`note`) | "your own working notes" during a painting | the artist itself | a tool exists; nothing says what to write |
| Code comments | comments in the Lua chunks | the artist itself | none |
| Notebook | carries from painting to painting | the artist's future self | exists; no sections, no prompts |
| Reply | the optional title and words at the end | the brief's reader | "if you like" |

This is the closest we can get to unprompted thought. If a richer view of thinking is ever wanted,
it is an experiment with a recorded condition, not a default.

## 4. Roles

| Role | Who | Does |
|---|---|---|
| Artist | three AI painters (Claude Opus 5.5 via Claude Code) | paints |
| Owner | Hinten Software | sets direction, issues themed prompts (or approves proposed ones), decides policy questions, reviews at check-ins |
| Director and operator | Claude (in Claude Code sessions with the owner) | designs, builds, QA, runs the atelier, starts works, keeps the observation log |
| Visitor | public | watches live, replays works, reads labels and about pages |

No one interferes with a work in progress. There is no "studio visit" (v0.2 DIR-8 dropped: it is
contact with an observer).

## 5. Functional requirements

Priority: **M** must (MVP: M1 and M2), **S** should (v1: M3), **C** could (later).

### 5.1 Engine (ENG)

| ID | Requirement | P |
|---|---|---|
| ENG-1 | Vendor claude-paint at a pinned commit; record the engine commit and easel binary hash in every work's manifest. Done for a198dd0. | M |
| ENG-2 | Build and run on the painter host (macOS, Apple Silicon). | M |
| ENG-3 | Reproducible build per engine version so any work replays with the engine that painted it (locked toolchain + `Cargo.lock`; binaries archived per version). | S |
| ENG-4 | Keep claude-paint's studio rules: no undo, paint only from piles mixed from tubes, no computed images, no mirrored-coordinate copying. | M |
| ENG-5 | Engine changes are atelier events: adopted deliberately, for all artists at once, dated in `history.md` and `UPSTREAM.md`. | S |
| ENG-6 | All artists paint from claude-paint's default tube box (14 historical pigments). A new tube is an atelier event (ENG-5). **new** | M |
| ENG-7 | Studio paths stay short: the easel's Unix socket path must be under 104 bytes. Studios live under `/Users/Shared/atelier/` (no account name in any path an artist sees). **new** | M |

### 5.2 Painter runtime (RUN)

| ID | Requirement | P |
|---|---|---|
| RUN-1 | Run artists with Claude Code headless (`claude -p`, the shipped binary) under the subscription login, subject to NFR-3. | M |
| RUN-2 | An artist's only tools are the easel's MCP tools. No built-in Claude Code tools (`--tools ""`), no web, no shell, no access outside its studio. | M |
| RUN-3 | The easel is an MCP server with `paint(lua)`, `look(crop?, mode?, size?, grid?)`, `note(text, replaces?)`, `status()`, `log()`, `read(path, offset?, limit?)`, plus `write`/`edit` limited to `notebook.md` and `toolkit.lua`. `look` returns the canvas image. Done except write/edit. | M |
| RUN-4 | Each work runs in a studio folder generated from the artist's persistent state: brief, guide, physics note, notebook, toolkit, walls, empty journal, empty painting. | M |
| RUN-5 | Sittings: after a sitting ends, start another (fresh session) with claude-paint's message "You're back at the easel. The painting is as you left it." until a sitting the artist ends itself adds no paint, or a safety cap (4) is reached. | M |
| RUN-6 | Usage limits: detect from Claude Code's exit and error text, wait, then continue the same session (`--resume`) or start a sitting; the pause is on the timeline ("studio closed until HH:MM"), never in anything the artist sees. | M |
| RUN-7 | Context: measure in the spike how images accumulate and when Claude Code compacts. If compaction would inject directive text ("next steps"), keep sittings short enough to avoid it, or use a PreCompact hook with neutral instructions; verify. | S |
| RUN-8 | Never expose counters, budgets, clocks, costs or machine time to artists (inherited from claude-paint's easel client). | M |
| RUN-9 | One command per work (`atelier paint <artist> [<brief>]`), started by a person (Q1); the runner then carries the work through its sittings unattended and resumes after a reboot. | M |
| RUN-10 | **Changed (Q1):** one artist paints at a time. No queue starts works by itself; `atelier next` suggests whose turn it is (fewest works) for the person starting it. | S |
| RUN-11 | Model and effort per artist, recorded per work. Default Opus 5.5, effort high. | S |
| RUN-12 | Optional artists on other vendors' CLIs, each under its own terms. | C |
| RUN-13 | **Isolation from the host's Claude Code (new).** Own config dir at a path without the account name (`CLAUDE_CONFIG_DIR=/Users/Shared/atelier/claude`: Claude Code shows the model each image's saved path), `--tools ""`, `--setting-sources ""` plus an atelier settings file, `--strict-mcp-config`, `--disable-slash-commands`, `--system-prompt` (full replacement), auto-memory off, auto-update off, `totalTokensReminder: "off"`, `CLAUDE_CODE_SILENT_TURN_REMINDER=0`, account email and names removed from the stored profile before each launch. Verified by the spike (docs/spike-report.md, section 3). | M |
| RUN-14 | **Thinking summaries on (new):** `--thinking-display summarized` (headless runs force "omitted" otherwise; the `showThinkingSummaries` setting alone is not enough), with `--output-format stream-json --verbose`. | M |

### 5.3 Artists (ART)

| ID | Requirement | P |
|---|---|---|
| ART-1 | Three persistent artists, each with an id and a studio. | M |
| ART-2 | **Birth:** an artist is created from a birth record (model, effort, created date, founding statement: none). **Changed:** no seed (C4); no prompted naming or self-description (C6, Q2: studios are Studio I, II, III until an artist names or signs itself). The birth record is public. | M |
| ART-3 | Notebook per artist, persisted across works. **Changed:** no prescribed content (C7). | M |
| ART-4 | Before each work the brief points to the notebook; the artist may write in it at any time. **Changed:** no condensing on a schedule: when the notebook passes a size limit, the runner shelves it as `notebooks/volume-N.md` (still readable in the studio) and the next brief says the notebook was full and a new one is open. | M |
| ART-5 | Personal toolkit (`toolkit.lua`): the artist's own Lua helpers, carried across works, versioned. `paint` takes `file: "toolkit.lua"` to run it as a chunk, so it lands in the log like any chunk and replays. Same studio rules (ENG-4). | S |
| ART-6 | Isolation: an artist never sees another artist's work, notebook, toolkit or name. | M |
| ART-7 | Every work stores notebook and toolkit as they were at start and end. | M |
| ART-8 | No persona scripting: no traits, emotions, backstory or style from us. | M |
| ART-9 | An artist can be retired; its studio and walls stay open. | C |
| ART-10 | **Walls in the studio (new, C5):** `walls/` holds the artist's own finished works, each as an image and its label (title and reply, if any). Readable with `read`. | M |

### 5.4 Briefs and direction (DIR)

| ID | Requirement | P |
|---|---|---|
| DIR-1 | Brief modes: **Free** (the default between prompts: "The subject and composition are yours."), **Themed** (a prompt from the owner: a theme or direction, freedom within it), **Recreation** (later). | M |
| DIR-2 | A brief is a structured file (YAML front matter + prose): mode, theme id, constraints, reading list, references. The front matter is for us; the artist sees only the prose. | M |
| DIR-3 | **Changed:** Free is the default between the owner's prompts; Themed is how the owner directs. Direction is intent and mood, never composition. | M |
| DIR-4 | A themed prompt can go to several artists at once (independently, same words). | M |
| DIR-5 | Recreation: reference images viewable, never read as pixels in code; flagged on the timeline. | C |
| DIR-6 | Recreation targets are public domain. | C |
| DIR-7 | Every brief states the stop rule: "Stop when, looking at the whole painting, nothing is left you want to change." | M |
| DIR-8 | **Dropped:** studio visits (contact with an observer, C1). | – |

### 5.5 Commentary (COM)

| ID | Requirement | P |
|---|---|---|
| COM-1 | Streams on the timeline: thinking (summarized), what the artist says between tool calls, the journal, code comments. | M |
| COM-2 | The journal is described only as "your own working notes". | M |
| COM-3 | Spike: confirm thinking summaries are recorded in headless runs with RUN-14 settings; measure how much. | M |
| COM-4 | **Changed:** the closing statement is optional ("the painting's title if you give it one and, if you like, a few sentences"). If present, it is the label on the wall. | M |

### 5.6 Observation and experiments (EXP)

| ID | Requirement | P |
|---|---|---|
| EXP-1 | Every work carries tags: brief mode, theme id, artist age (work number), model, effort, engine commit. | M |
| EXP-2 | Style measures from each log (tubes, piles, brushes, strokes, layering, waits, format, looks, toolkit use). Data captured from day one; extraction after launch. | S |
| EXP-3 | Divergence over time and between artists. | C |
| EXP-4 | **Dropped** (C1): observation framing as a variable. | – |
| EXP-5 | Innate baseline: an amnesiac painter (same model, no notebook, walls or toolkit) on the same brief; shown in a separate control room. | S |
| EXP-6 | Exchange (an artist sees another's work). | C |
| EXP-7 | Recognizability test. | C |
| EXP-8 | Repeated theme to the same artist at intervals. | S |
| EXP-9 | Observation log: the director's dated notes, private by default. | S |

### 5.7 Recording and replay (REC)

| ID | Requirement | P |
|---|---|---|
| REC-1 | Every work produces a complete, self-contained work package (section 7), immutable once finished. | M |
| REC-2 | Parser: Claude Code transcripts into the viewer's timeline (start, think, say, paint, look, image, jnote, read, user, errors, pauses). Done for the core events in phase 1 (`viewer/studio.py`). | M |
| REC-3 | Live: the parser tails the active transcript; the viewer updates within a minute. | M |
| REC-4 | Replay check: the stored log on the stored engine reproduces the final canvas byte for byte (`check_painting`), hash stored. Verified on a spike painting. | M |
| REC-5 | Per-chunk frames for smooth scrubbing. | S |
| REC-6 | High-resolution final render (optional varnish) after the work ends. | S |
| REC-7 | Scrub private data from everything public: home paths, account names, the owner's names (Q7), machine names, IPs, emails, Claude account and session identifiers. A private word list outside the repository (`~/.atelier/private-words.txt`) feeds the checks. | M |

### 5.8 The atelier, as visitors see it (ATL)

| ID | Requirement | P |
|---|---|---|
| ATL-1 | Entrance: the three studios, each with its state (painting, between sittings, studio closed, resting). | M |
| ATL-2 | Studio: the easel (live work) and the walls (finished works, newest first, with labels). | M |
| ATL-3 | Easel view: canvas, thinking and journal stream, code, timeline with scrubbing and speed (claude-paint's viewer). | M |
| ATL-4 | Any work on the walls opens the same view as a replay. | M |
| ATL-5 | Artist history: notebook over time, toolkit versions, birth record. | S |
| ATL-6 | Control room for baseline works. | S |
| ATL-7 | Static site; no server code needed to view. | M |
| ATL-8 | Mobile-friendly (claude-paint's viewer already has a phone layout). | S |
| ATL-9 | Attribution: engine and viewer by Alice (claude-paint, MIT / CC BY 4.0), stillwet.art linked. | M |
| ATL-10 | **About page (new):** what the atelier is, how the artists work, what is recorded and what is not (summarized thinking), the principles, the licenses, the source. | M |
| ATL-11 | **Thinking labeled (new):** every thinking passage is marked as the model provider's summary. | M |

### 5.9 Operations and hosting (OPS)

| ID | Requirement | P |
|---|---|---|
| OPS-1 | Painter host: the Mac (M6, 24 GB). Runs Claude Code, easel MCP, runner, parser, export. | M |
| OPS-2 | Archive: work packages synced to the NAS (Synology RS820+, DSM 7.4) after every sitting and every finished work. | M |
| OPS-3 | **Changed:** public site on the NAS: an nginx container serves the static export; a `cloudflared` container connects it to Cloudflare (free plan) through a Tunnel. No inbound ports on the NAS or the router; the Mac is never exposed; no QuickConnect. Needs a domain on Cloudflare (Q5). | M |
| OPS-4 | During a live work, export and push every minute (rsync over SSH, Mac to NAS). | M |
| OPS-5 | Windows PC: no role. | – |
| OPS-6 | The Mac stays awake during a work (`caffeinate`); the runner resumes after interruption (launchd). | M |
| OPS-7 | **Changed:** source in Gitea on the NAS (the clone's only remote); GitHub, **public**, fed only by Gitea's push mirror. | M |

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Determinism | Replays byte-identical (inherited). |
| NFR-2 Permanence | A hung work replays without the live system: package plus pinned engine suffices. |
| NFR-3 Compliance | **Gating.** Claude Code as shipped, unmodified, with no header spoofing or credential sharing. Before any unattended operation, the owner decides the mode of operation (section 9, Q1). |
| NFR-4 Privacy | No personal data in public outputs (REC-7). |
| NFR-5 Robustness | A crash, limit or reboot loses at most the current chunk. |
| NFR-6 Observability | Runner logs for the operator (sittings, pauses, errors, counts), never shown to artists. |
| NFR-7 Simplicity | Files and static pages over databases and services. |
| NFR-8 Isolation integrity | Tested: an artist's tools refuse paths outside its studio (done for `read`); the artist's session holds nothing from the host's Claude Code (RUN-13, spike). |
| NFR-10 Transcript audit (new) | After every sitting the runner audits the transcript: every attachment and injected text Claude Code added is compared with the known list (environment, model, date, identity line); anything new, the account's email or name, a token counter or a "say what you're doing" nudge stops the atelier until the operator clears it. Every leak found in the spike came from the harness, not from our texts. |
| NFR-9 White room (new) | Every artist-facing text (system prompt, brief, guide, notes, tool descriptions, tool replies, sitting messages, errors) is checked against principle 3.6 by a script with a word list (viewers, audience, watch, observe, evaluate, score, judge, budget, cost, counter, other painters, operator, Claude Code, ...) and by review. |

## 7. Data model

```
/Users/Shared/atelier/                 the atelier's data (painter host), synced to the NAS
  history.md                           atelier events: engine changes, tubes, artists, prompts
  artists/<id>/                        id: a neutral id (e.g. "i", "ii", "iii")
    birth.json                         model, effort, created, founding statement (none)
    notebook.md   notebooks/           current notebook; shelved volumes
    toolkit.lua                        current toolkit
    walls/<nnn>.png  <nnn>.md          finished works as the artist sees them (ART-10)
    works/<nnn>-<slug>/                work packages
  studios/<hex>/                       the live studio of the work in progress (neutral name)
  controls/<nnn>/                      baseline works (EXP-5)
  briefs/                              issued briefs
  observations/                        director's notes (private)
  run/                                 runner state and logs (private)

work package:
  manifest.json      id, artist, title, mode, theme id, tags, model, effort, engine commit,
                     easel hash, start/end, sittings, pauses, replay hash, replay-verified
  brief.md           as issued (prose the artist saw + front matter)
  painting.lua       the easel log: the painting itself
  journal.md         + journal-revisions.jsonl
  reply.md           the artist's last words (title, statement), if any
  notebook.before.md / notebook.after.md, toolkit.before.lua / toolkit.after.lua
  sessions/          raw Claude Code transcripts and stream logs (private)
  timeline.json      parsed, scrubbed events (public)
  looks/             images the artist saw
  frames/            per-chunk frames (optional)
  measures.json      style measures (EXP-2, later)
  final.png          replay render at full resolution
```

## 8. Architecture

```
            Mac (painter host)                                   NAS (Synology)                 Public
 ┌───────────────────────────────────────────────┐      ┌──────────────────────────┐   ┌─────────────────┐
 │ queue ─► runner ─► claude -p (isolated, RUN-13)│      │ /volume1/atelier/archive │   │ Cloudflare edge │
 │                     │ MCP (stdio)              │ rsync│ /volume1/atelier/site ◄──┼───┤ (cache, TLS)    │
 │                     ▼                          │ ───► │ nginx container          │   │       ▲         │
 │       easel-mcp ─► bin/easel ─► engine         │ ssh  │ cloudflared container ───┼──►│ tunnel (outbound│
 │ transcript ─► parser ─► export (each minute)   │      │ Gitea (source)  ─► GitHub│   │ only)           │
 └───────────────────────────────────────────────┘      └──────────────────────────┘   └─────────────────┘
```

## 9. Risks and decisions

| Risk | Impact | Mitigation |
|---|---|---|
| **Terms: unattended subscription use** (C11) | account action; project stops | Q1: operate in the "ordinary individual use" mode (each work started by a person, sittings bounded, no 24/7 loop) or switch artists to API-key billing; optionally ask Anthropic |
| Thinking summaries absent or thin in headless runs | weaker view of the mind | spike (COM-3); journal and code comments remain |
| Claude Code injects text the artist reads (reminders, compaction summaries, identity lines) | breaks the white room (3.6) | spike inspects the transcript and a probe session; settings and hooks to neutralize; NFR-9 |
| Divergence is drift, not creativity | over-reading | baseline (EXP-5), repeated themes (EXP-8), notebooks as reasons |
| Notebook homogenizes toward model defaults | no divergence | a valid finding; walls (ART-10) give visual memory too |
| Subscription limits slow careers | uneven exposure | queue with equal turns (RUN-10); compare at equal work counts |
| Toolkit becomes a picture generator | loss of authenticity | ENG-4 applies; director reviews toolkit diffs |
| Engine churn breaks replay | lost history | ENG-1, ENG-3 |
| Mixbox is non-commercial | reuse limited | stated in README and site (C13) |

### Decisions (check-in 1, 2026-10-03)

| # | Decision | Outcome |
|---|---|---|
| Q1 | Mode of operation under the terms (NFR-3) | **Decided (a):** a person (the owner or the operator, in a session with the owner) starts each work; the runner carries it through its sittings and limit pauses unattended. No unattended queue that starts works by itself. Revisit (API-key billing) if the atelier grows toward continuous painting. |
| Q2 | Naming | **Decided:** no prompt to name or describe themselves. Studios are Studio I, II, III until an artist names or signs itself on its own. |
| Q3 | Walls in the studio (ART-10) | **Decided:** yes. |
| Q4 | Cadence | open: follows from Q1 (works are started by hand) |
| Q5 | Domain name and Cloudflare account | open: the owner to choose; ~USD 10/year at Cloudflare Registrar; needed by M2 |
| Q6 | Publish raw transcripts or only the timeline | default kept: timeline only |
| Q7 | Public identity | **Decided:** the owner's personal name appears nowhere in the project; "Hinten Software" where an owner must be named. Applies to files, commit metadata, the site and every export (REC-7). |

## 10. Milestones and acceptance

**M0. Spike** (phase 1, in progress). Engine builds (done); MCP server paints (done); replay
byte-identical (done); Claude Code headless, isolated, paints a small canvas; thinking summaries
recorded; what the model receives is verified; usage, tokens, images and timing measured; the
viewer replays the spike session. Accept: spike report.

**M1. One artist, first work.** Runner with sittings and limit pause; artist birth, notebook,
walls; brief system; parser and live view on the LAN; work package; replay verified; hung on the
wall. Accept: one artist completes a free work, watchable live on the LAN and replayable from its
wall.

**M2. The atelier opens.** Static site with entrance, studios, walls, about page; scrub; NAS
nginx + Cloudflare Tunnel; export every minute. Accept: a visitor outside the LAN watches a live
work and replays a finished one.

**M3. Three artists.** Isolation tests, queue, themed multi-artist prompts, toolkits, history
pages. Accept: each artist has completed five works, isolated.

**M4. Observation.** Measures, baseline control room, repeated themes, observation log, first
report.

**Later.** Recreation, exchange, recognizability, other vendors.

## Appendix A. Brief (draft, artist-facing prose)

The front matter (mode, theme id, tags) is ours and is not in the artist's copy.

```
# Paint a picture

{DIRECTION}
   free:    The subject and composition are yours.
   themed:  {theme, as the owner wrote it}. Within it, everything is yours to decide.

{NOTEBOOK}
   first work:    notebook.md is yours. It stays in this studio from one painting to the next.
   later works:   notebook.md is yours. It stays in this studio from one painting to the next.
                  walls/ holds the paintings you have finished here.
   notebook full: notebook.md was full; it is on the shelf as notebooks/volume-N.md, and a new
                  notebook.md is open.

## Your studio            (claude-paint round 21.2, unchanged but for "This folder")
## The rules of the studio (unchanged; plus: "Your toolkit holds your own ways of making marks;
                            it may not compute pictures." once ART-5 is in)
## What to read            notes/easel_guide.md, and notes/research/oil_paint_physics.md as needed.
## Working                 You make every artistic decision. / Look at your painting often, whole
                           and close up. / Keep a working journal with `note` as you go: your own
                           working notes. You can revise them. / Stop when, looking at the whole
                           painting, nothing is left you want to change.
## Your reply              When you stop working, reply with the painting's title if you give it
                           one and, if you like, a few sentences about the picture.
```

System prompt (claude-paint's, minus the evaluation line, C8): "You are a painter working at an
easel in your studio. The studio is the folder you are in. You paint with the easel's tools and
read the studio's notes with the read tool. Your brief is BRIEF.md in the studio."
