from typing import Optional

from bot.database.sqlite import get_connection


def upsert_user(conn, user_id: int, username: Optional[str]) -> None:
    conn.execute(
        """
        INSERT INTO users (user_id, username, role, is_subscribed, created_at, updated_at, last_seen_at)
        VALUES (?, ?, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            updated_at=CURRENT_TIMESTAMP,
            last_seen_at=CURRENT_TIMESTAMP
        """,
        (user_id, username),
    )


def set_role(conn, user_id: int, role: str) -> None:
    conn.execute(
        """
        INSERT INTO users (user_id, role, is_subscribed, created_at, updated_at)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            role=excluded.role,
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id, role),
    )


def get_user_role(conn, user_id: int) -> Optional[str]:
    cur = conn.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def list_subscribers(conn):
    cur = conn.execute(
        "SELECT user_id, role FROM users WHERE is_subscribed = 1 AND role IS NOT NULL"
    )
    return cur.fetchall()
