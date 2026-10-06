# notes — "leave a note" for notart.fyi

A Cloudflare Worker on `notart.fyi/api/notes*` that stores visitor notes in D1
and keeps bots out with Turnstile. The site itself stays on the NAS behind the
Cloudflare Tunnel; only this path is answered by the Worker, so the page calls
it same-origin (no CORS).

Privacy: no cookies, no analytics, and nothing about a visitor is stored — no
IP, user agent, country or other header. Rate limiting keeps only
`HMAC-SHA256(RATE_SECRET + UTC date, IP)` cut to 128 bits, with counts. Because
the key changes every day, a visitor cannot be followed from one day to the
next, and rows older than two days are deleted.

Hostile notes stay. The owner hides only spam and illegal content (see
[Hiding a note](#hiding-a-note)).

Operator: Hinten Software.

## Files

| File | Purpose |
| --- | --- |
| `worker.js` | The Worker (ES module, no build step) |
| `schema.sql` | D1 tables `notes` and `rate` with indexes |
| `wrangler.toml.example` | Config template; copy to `wrangler.toml` (git-ignored) |
| `hide.sh`, `unhide.sh` | Hide or show a note by id |
| `test/worker.test.mjs` | Tests: `node --test deploy/notes/test/` (Node 22.13+ for `node:sqlite`) |

## API

All responses are JSON with `X-Content-Type-Options: nosniff`. Errors are
`{"error": "<short sentence>"}` with `Cache-Control: no-store`.

### `GET /api/notes?work=<id>&before=<cursor>`

Both parameters optional. Without `work` you get the whole wall; with it, the
notes for that work (`^[a-z]+-\d{3}$`, e.g. `field-012`). Newest first, 50 per
page, hidden notes never included.

```json
200  Cache-Control: public, max-age=30
{
  "notes": [
    { "id": 42, "at": "2026-10-06T07:31Z", "work": "field-012", "text": "…" },
    { "id": 41, "at": "2026-10-06T07:02Z", "work": null, "text": "…" }
  ],
  "next": "41"
}
```

`at` is UTC to the minute. `next` is the cursor for the following page (pass it
as `before`), or `null` on the last page. Bad `work` or `before` → 400.

Because of the 30 s cache, a visitor may not see their own note on reload
right away; the page should add the posted note locally from the 201 response.

### `POST /api/notes`

```json
{ "text": "…", "work": "field-012", "token": "<Turnstile token>" }
```

`work` may be omitted or `null` for the wall.

| Status | Body | When |
| --- | --- | --- |
| 201 | `{"id": 43, "at": "2026-10-06T07:32Z"}` | stored |
| 400 | `{"error": "Please write something."}` | text missing or empty after cleaning |
| 400 | `{"error": "Notes can be at most 500 characters."}` | |
| 400 | `{"error": "Links are not allowed."}` | |
| 400 | `{"error": "Unknown work."}` | `work` does not match `^[a-z]+-\d{3}$` |
| 400 | `{"error": "That note is too long."}` | request body over 4 KB |
| 400 | `{"error": "Could not read the note."}` | not a JSON object |
| 403 | `{"error": "Please complete the check first."}` | token missing or over 2048 chars |
| 403 | `{"error": "The check failed. Please try again."}` | Turnstile said no |
| 429 | `{"error": "You have left a lot of notes. Please wait a while."}` | over 5/hour or 20/UTC day; `Retry-After: 3600` |
| 503 | `{"error": "The check is not available right now. Please try again."}` | siteverify unreachable |

Any other method on `/api/notes` → 405 (`Allow: GET, POST`); any other path → 404.

Text handling, in order: line breaks normalised to `\n`; control characters
other than `\n` removed (tabs included), as are zero-width spaces and bidi
override characters that could hide a link; trailing spaces on a line removed;
runs of more than 3 newlines cut to 3; trimmed. The result must be 1–500 code
points (an emoji counts as one).

Link rule: a note is rejected if it contains `http://`, `https://`, `www.`, or
a bare domain — dot-separated labels ending in a 2–24 letter part written all
lower case or all upper case (or an `xn--` punycode part). So `example.com`,
`foo.xyz`, `EXAMPLE.COM`, `bücher.de` and `me@mail.example.net` are rejected,
while `This is slop. Really.`, `slop.Really`, `e.g.`, `Wait...what` and
`1.2.3` pass. The trade-off: file names like `image.png` and run-together
lower-case words like `ok.so` are rejected too.

### The page

Load Turnstile and render the widget with the site key from step 4 below:

```html
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<div class="cf-turnstile" data-sitekey="TURNSTILE_SITE_KEY"></div>
```

Replace `TURNSTILE_SITE_KEY` with the real key. For local testing use
Cloudflare's always-pass test key `1x00000000000000000000AA` (with the test
secret `1x0000000000000000000000000000000AA` in `.dev.vars`). Send the widget's
token as `token`; tokens are single-use, so reset the widget after each post
(`turnstile.reset()`).

## Deploy

You need a Cloudflare account with the `notart.fyi` zone on it. Run everything
from `deploy/notes/`. `npx wrangler` fetches wrangler on demand; nothing needs
installing globally.

1. **Log in** (interactive) — `npx wrangler login`. For a non-interactive
   deploy, see [API token](#api-token-for-non-interactive-deploys) instead.

2. **Create the database and config**

   ```sh
   npx wrangler d1 create atelier-notes
   cp wrangler.toml.example wrangler.toml
   # paste the printed database_id into wrangler.toml
   ```

3. **Apply the schema**

   ```sh
   npx wrangler d1 execute atelier-notes --remote --file schema.sql
   ```

4. **Create the Turnstile widget** — Dashboard → Turnstile → Add widget.
   Hostname `notart.fyi`, mode *Managed*. Note the **site key** (public, goes
   into the page as above) and the **secret key** (for the next step only).

5. **Set the secrets**

   ```sh
   npx wrangler secret put TURNSTILE_SECRET   # the Turnstile secret key
   openssl rand -base64 32 | npx wrangler secret put RATE_SECRET
   ```

   `RATE_SECRET` is any long random string; nobody needs to know it. Changing
   it just resets everyone's rate limit.

6. **Deploy**

   ```sh
   npx wrangler deploy
   ```

   This uploads `worker.js`, attaches the route `notart.fyi/api/notes*` and the
   daily cron. Check with `curl -s https://notart.fyi/api/notes`.

The Worker route takes precedence over the tunnel for `/api/notes*` only; the
rest of the site keeps coming from the NAS. Workers logs are left off in
`wrangler.toml` (`observability.enabled = false`) so request metadata is not
kept there either; avoid `wrangler tail` except for debugging.

### API token for non-interactive deploys

Create a custom token (Dashboard → My Profile → API Tokens → Create Custom
Token) with:

| Scope | Permission | Needed for |
| --- | --- | --- |
| Account | Workers Scripts — Edit | upload the Worker, secrets, cron trigger |
| Account | D1 — Edit | create the database, apply schema, `hide.sh` / `unhide.sh` |
| Zone (notart.fyi) | Workers Routes — Edit | attach `notart.fyi/api/notes*` |
| Account | Account Settings — Read | wrangler looks up the account |

Then:

```sh
export CLOUDFLARE_API_TOKEN=…   # the token
export CLOUDFLARE_ACCOUNT_ID=…  # from the dashboard sidebar; keep it out of git
npx wrangler deploy
```

Notes on the list (checked against Cloudflare's token docs and the
*Edit Cloudflare Workers* template, which contains Workers Scripts, Workers
Routes and Account Settings plus KV, R2, Tail, User Details and Memberships):

- The four permissions above are enough for this Worker. KV and R2 are not used.
- `wrangler whoami` needs **User Details — Read** (user scope); add it if you
  want that command to work with the token. Without `CLOUDFLARE_ACCOUNT_ID`
  wrangler may also need **User Memberships — Read** to find the account, so
  set the variable.
- `wrangler tail` would need **Workers Tail — Read**; not needed for deploys.
- Creating the Turnstile widget is done once in the dashboard; doing it by API
  would need an extra Turnstile permission on the token.
- Restrict the token to this account and the `notart.fyi` zone.

## Hiding a note

Find the id (it is in every note the API returns), then:

```sh
./hide.sh 42      # hidden = 1, disappears within ~30 s (cache)
./unhide.sh 42    # back again
```

Both use `npx wrangler d1 execute atelier-notes --remote --command …` and need
`wrangler.toml` here plus a login or the API token above. Set `NOTES_DB` if the
database is named differently. To review recent notes, including hidden ones:

```sh
npx wrangler d1 execute atelier-notes --remote \
  --command "SELECT id, at, work, hidden, text FROM notes ORDER BY id DESC LIMIT 50"
```

To remove a note for good: `--command "DELETE FROM notes WHERE id = 42"`.

There is deliberately no admin HTTP endpoint.

## Tests

```sh
node --test deploy/notes/test/
```

The tests run the Worker against an in-memory SQLite database (via
`node:sqlite`, applying `schema.sql`) shaped like the D1 API, with Turnstile
stubbed. They cover posting, validation, link rejection, Turnstile failure and
outage, hourly and daily limits, pruning, pagination, the work filter, hidden
notes, routing, and that no IP, user agent, country or other header ends up in
the database.
