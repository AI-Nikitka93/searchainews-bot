CREATE TABLE IF NOT EXISTS channel_post_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_channel_post_keys ON channel_post_keys(channel_id, dedupe_key, sent_at);
