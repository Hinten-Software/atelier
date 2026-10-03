# Independent review of requirements v0.4, and the response

2026-10-03. Reviewer: a separate Claude agent with no part in writing the requirements, read-only,
given the documents, the spike code and the upstream project, and the owner's fixed intent.
Verdict: "Not ready for M1 implementation yet": two blockers, and the runner and studio
specification missing. v0.5 answers every finding; the table gives where.

| # | Severity | Finding (short) | Response in v0.5 |
|---|---|---|---|
| R1 | blocker | the painter's easel binary holds the account's home path (69 times) and is readable from the studio | fixed and verified: `tools/build-engine.sh`; ENG-7; `read` refuses `bin/` and binaries (RUN-3) |
| R2 | blocker | RUN-13 claimed verified while the spike left the login, email and paths open; no limit or resume test | M0 marked incomplete; probe suite RUN-16 gates birth; M1 acceptance 1 |
| R3 | major | the audit runs after the artist has read a leak; no contamination handling | NFR-10: live audit, kill, contamination rules |
| R4 | major | re-offering the easel after the artist stops overrides its judgement of "done" | C18, RUN-5: a voluntary end finishes the work |
| R5 | major | paths reveal an institution, other studios and change per work | C19, section 7: one stable studio per artist at a neutral root |
| R6 | major | the runner used the auto-updating Claude Code install | RUN-15 pinned binary; ENG-5 |
| R7 | major | manifest lacks harness versions, hashes, dates shown | section 7 manifest; ENG-5 widened |
| R8 | major | a limit message may stay in history on resume; resume text unspecified | RUN-6: always a fresh sitting; give-up rule |
| R9 | major | compaction, MCP timeout and output caps can inject text | RUN-7 compaction off with a context threshold; RUN-13 timeout and output limit; RUN-3 reply caps; RUN-16 5-minute chunk |
| R10 | major | the artist cannot list `walls/`; studio layout unspecified | RUN-3 folder listing, ART-10 `walls/index.md`, section 7 |
| R11 | major | "operator starts works" vs Q1; launchd resume without a person | section 4, RUN-9 `started_by`, C20 |
| R12 | major | resume after reboot can't reach the login keychain | C20: a person resumes; setup-token preferred (RUN-13) |
| R13 | major | no runner state machine | section 5.10 |
| R14 | major | scrub too narrow; private files inside exported packages | REC-7, REC-8 allowlist; private store mode 700 |
| R15 | major | viewer still stillwet-branded; no visitor privacy or legal notice | ATL-9, ATL-12, Q8 |
| R16 | major | no security requirements for the public site | OPS-8, ATL-13 |
| R17 | major | the NAS mirror is not a backup | OPS-9, Q9 |
| R18 | major | the public site can train future models about the atelier; model retirement | REC-9, ART-11 |
| R19 | major | the date and other signals reach the artist, undeclared | section 3.2 accepted signals; date recorded |
| R20 | major | the white-room check scans sources, not what the artist receives | NFR-9 (prepared studio and messages), NFR-10 (transcript) |
| R21 | major | late baselines don't compare with early careers | EXP-5 controls from M3 at fixed intervals |
| R22 | major | M1 acceptance doesn't exercise the hard parts | section 10, nine checks |
| R23 | minor | stale and inconsistent text | cleaned in the rewrite |
| R24 | minor | `write`/`edit` unspecified | RUN-3, ART-4, revision log |
| R25 | minor | walls content and gallery vocabulary | ART-10: neutral file names, unvarnished render, finished works only |
| R26 | minor | owner and director influence not logged | EXP-10 intervention policy |
| R27 | minor | "performative" not measurable under C1 | section 1 says so; EXP-11 addressee markers |
| R28 | suggestion | defer frames, control room, shelving; 2-minute export; stop the work, not the atelier | REC-5, ATL-6, ART-4 deferred; OPS-4 2 min; NFR-10 stops the sitting |
