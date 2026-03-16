PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  role TEXT,
  language TEXT NOT NULL DEFAULT 'ru',
  is_subscribed INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  raw_summary TEXT,
  full_text TEXT,
  impact_score INTEGER,
  impact_rationale TEXT,
  action_items_json TEXT,
  target_role TEXT,
  tags_json TEXT,
  published_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deliveries (
  user_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'sent',
  sent_at TEXT NOT NULL DEFAULT (datetime('now')),
  error TEXT,
  PRIMARY KEY (user_id, item_id),
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS webhook_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  req_id TEXT,
  authorized INTEGER,
  update_id INTEGER,
  chat_id TEXT,
  username TEXT,
  kind TEXT,
  chat_type TEXT,
  message_id INTEGER,
  command TEXT,
  text TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bot_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  update_id INTEGER,
  chat_id TEXT,
  username TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bot_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  update_id INTEGER,
  chat_id TEXT,
  username TEXT,
  event TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS request_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  req_id TEXT,
  path TEXT,
  method TEXT,
  status INTEGER,
  authorized INTEGER,
  header_present INTEGER,
  path_secret_present INTEGER,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  item_id INTEGER NOT NULL,
  sent_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_items_role_score ON items(target_role, impact_score);
CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_user ON deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_score_date ON items(impact_score, published_at, created_at);
CREATE INDEX IF NOT EXISTS idx_users_subscribed ON users(is_subscribed);
CREATE INDEX IF NOT EXISTS idx_channel_posts_channel ON channel_posts(channel_id, sent_at);
