import sqlite3
from pathlib import Path


USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT,
    is_subscribed INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT
);
"""

DELIVERIES_TABLE = """
CREATE TABLE IF NOT EXISTS deliveries (
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_id)
);
"""


def apply_migrations(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(USERS_TABLE)
        conn.execute(DELIVERIES_TABLE)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_user ON deliveries(user_id)")
