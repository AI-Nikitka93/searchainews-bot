CREATE TABLE IF NOT EXISTS webhook_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  req_id TEXT,
  authorized INTEGER,
  update_id INTEGER,
  chat_id TEXT,
  username TEXT,
  kind TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
