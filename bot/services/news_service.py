from typing import List


ROLE_FALLBACKS = {"all", "other", "any"}


def get_latest_for_role(conn, role: str, limit: int = 3) -> List[dict]:
    query = """
        SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role, tags_json, published_at
        FROM items
        WHERE impact_score IS NOT NULL
          AND impact_score >= 3
          AND (
                target_role IS NULL
                OR target_role = ''
                OR lower(target_role) = ?
                OR lower(target_role) IN ('all', 'other', 'any')
              )
        ORDER BY COALESCE(published_at, fetched_at) DESC
        LIMIT ?
    """
    cur = conn.execute(query, (role.lower(), limit))
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_unsent_for_user(conn, user_id: int, role: str, limit: int = 5) -> List[dict]:
    query = """
        SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json,
               i.target_role, i.tags_json, i.published_at
        FROM items i
        LEFT JOIN deliveries d
          ON d.item_id = i.id AND d.user_id = ?
        WHERE d.item_id IS NULL
          AND i.impact_score IS NOT NULL
          AND i.impact_score >= 3
          AND (
                i.target_role IS NULL
                OR i.target_role = ''
                OR lower(i.target_role) = ?
                OR lower(i.target_role) IN ('all', 'other', 'any')
              )
        ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
        LIMIT ?
    """
    cur = conn.execute(query, (user_id, role.lower(), limit))
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def mark_delivered(conn, user_id: int, item_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO deliveries (user_id, item_id, sent_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (user_id, item_id),
    )
