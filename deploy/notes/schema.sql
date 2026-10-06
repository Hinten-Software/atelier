-- Visitor notes for notart.fyi. Apply with:
--   npx wrangler d1 execute atelier-notes --remote --file schema.sql

CREATE TABLE IF NOT EXISTS notes (
  id     INTEGER PRIMARY KEY,         -- also the pagination cursor
  at     TEXT    NOT NULL,            -- UTC, minute precision: 2026-10-06T07:31Z
  work   TEXT,                        -- null = wall, else e.g. 'field-012'
  text   TEXT    NOT NULL,
  hidden INTEGER NOT NULL DEFAULT 0   -- 1 = hidden by the owner (spam, illegal)
);

CREATE INDEX IF NOT EXISTS notes_wall ON notes (hidden, id DESC);
CREATE INDEX IF NOT EXISTS notes_work ON notes (work, hidden, id DESC);

-- Rate limiting. `key` is a truncated HMAC of the visitor IP under a secret
-- that changes every UTC day; the IP itself is never stored. One row per
-- key and hour; the daily total is the sum over the day's rows.
CREATE TABLE IF NOT EXISTS rate (
  key   TEXT    NOT NULL,
  day   TEXT    NOT NULL,             -- 2026-10-06
  hour  TEXT    NOT NULL,             -- 2026-10-06T07
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key, hour)
);

CREATE INDEX IF NOT EXISTS rate_day ON rate (day);
