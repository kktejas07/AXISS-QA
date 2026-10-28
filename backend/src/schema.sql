-- Waitlist signups captured by the "coming soon" page.
CREATE TABLE IF NOT EXISTS waitlist (
  id          SERIAL PRIMARY KEY,
  email       TEXT NOT NULL UNIQUE,
  source      TEXT DEFAULT 'coming-soon',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS waitlist_created_at_idx ON waitlist (created_at DESC);

-- Tiny key/value table so we can prove the database round-trip from the API.
CREATE TABLE IF NOT EXISTS app_meta (
  key         TEXT PRIMARY KEY,
  value       JSONB NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_meta (key, value)
VALUES ('app', '{"name":"AXISS QA","status":"coming-soon"}')
ON CONFLICT (key) DO NOTHING;
