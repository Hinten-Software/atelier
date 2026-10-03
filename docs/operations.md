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
