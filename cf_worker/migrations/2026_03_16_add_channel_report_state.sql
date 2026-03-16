CREATE TABLE IF NOT EXISTS channel_report_state (
  channel_id TEXT PRIMARY KEY,
  last_report_date TEXT NOT NULL
);
