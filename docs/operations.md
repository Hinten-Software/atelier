# Operations

## Source: Gitea master, GitHub mirror

- **Gitea** on the NAS (`atelier`) is the only remote of every clone (`origin`, the SSH host
  alias `gitea`). All pushes go there.
- **GitHub** `Hinten-Software/atelier` (public) is a push mirror written by Gitea and nothing else.
  No machine pushes to GitHub; the mirror deletes GitHub branches Gitea does not have, so
  nothing is ever committed on GitHub directly.
- **Mirror token:** `gitea-mirror-atelier-Hinten`, a fine-grained GitHub token, resource owner
  the Hinten-Software organization, access to `Hinten-Software/atelier` only, repository permission **Contents: Read and write** (Metadata: Read
  is added automatically), expiring on the shared date of the other mirror tokens. It lives only
  in the Gitea push mirror; a lost token is regenerated, never recovered.
- **Gitea settings:** repo > Settings > Repository > Mirror Settings > Push Mirror: URL
  `https://github.com/Hinten-Software/atelier.git`, username the token owner's GitHub account,
  password the token,
  **Sync when commits are pushed** on.
- **Check:** the mirror row's "Last update" is recent with no error, and GitHub's `main` is the
  same commit as Gitea's.

The same rule as the owner's other repositories.

## Running the atelier (runbook)

Everything below runs on the painter host (the Mac). `atelier` is `python3 runner/atelier.py`.

**Once, before the first artist (and after any harness change):**
1. `tools/build-engine.sh`: both easels, no local paths inside.
2. `~/atelier-data/bin/claude-<version>`: a copy of the Claude Code version the atelier pins
   (requirements RUN-15); the runner never uses the auto-updating install.
3. The login: `claude setup-token` by the owner, the token saved (by the owner, in an editor) to
   `~/atelier-data/secrets/claude-oauth-token`, mode 600. Nobody else reads or prints it.
4. `python3 runner/probes.py`: context, tools and long-chunk probes on the production setup. All
   must pass; the pass is recorded and `atelier birth` requires it.
5. `atelier birth`: Studio I (then II, III, each after the probes pass for the harness it will use).

**A work (requirements Q1: a person starts it):**
- `atelier next`: whose turn it is.
- `atelier paint <i|ii|iii> --by owner [--theme "..."]`: prepares the studio, scans it (NFR-9),
  starts the runner in the background. The terminal can close.
- `atelier status`: the open work, its state, how its sittings ended, any audit hits.
- The runner exports the site every 2 minutes; `atelier serve` shows it on the LAN at
  `http://<mac>:8800/studio/`.

**When something happens:**
- *Usage limit:* nothing to do; the runner waits for the reset and starts a fresh sitting.
- *Crash:* nothing to do; the runner retries after 90 s, 3, 5, 10, 15, 20 min, then stops the
  work as not finished.
- *Reboot or runner crash:* `atelier status` says `interrupted`; `atelier resume` continues it.
- *White-room audit stop:* `atelier status` lists the hits. Read the transcript in the work's run
  folder. Fix the cause (it is ours, not the artist's), log it, then either
  `atelier resume --clear "what was found and fixed"` (the work stays contaminated: not hung, not
  exported) or leave it. The artist's notebook edits from that sitting are already rolled back.
