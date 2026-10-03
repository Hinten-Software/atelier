# Operations

## Source: Gitea master, GitHub mirror

- **Gitea** `atelier` on the NAS is the only remote of every clone (`origin`,
  `the SSH host alias gitea`). All pushes go there.
- **GitHub** the GitHub mirror (public) is a push mirror written by Gitea and nothing else.
  No machine pushes to GitHub; the mirror deletes GitHub branches Gitea does not have, so
  nothing is ever committed on GitHub directly.
- **Mirror token:** `gitea-mirror-atelier`, a fine-grained GitHub token with access to
  the GitHub mirror only, repository permission **Contents: Read and write** (Metadata: Read
  is added automatically), expiring on the shared date of the other mirror tokens. It lives only
  in the Gitea push mirror; a lost token is regenerated, never recovered.
- **Gitea settings:** repo > Settings > Repository > Mirror Settings > Push Mirror: URL
  the GitHub repository's HTTPS URL, username the GitHub account, password the token,
  **Sync when commits are pushed** on.
- **Check:** the mirror row's "Last update" is recent with no error, and GitHub's `main` is the
  same commit as Gitea's.

The same rule as the owner's other repos (Cube Sweeper's `docs/dev-machine-setup.md`, "GitHub
mirrors"); add `atelier` to that table.
