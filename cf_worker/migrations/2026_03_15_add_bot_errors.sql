CREATE TABLE IF NOT EXISTS bot_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  update_id INTEGER,
  chat_id TEXT,
  username TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
