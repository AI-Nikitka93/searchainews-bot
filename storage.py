import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Iterable, Dict, Any, Optional, List


class SQLiteStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = self._ensure_db_path(db_path)
        self._init_db()

    @staticmethod
    def _ensure_db_path(db_path: str) -> str:
        expanded = os.path.expandvars(db_path)
        directory = os.path.dirname(expanded)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return expanded

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    item_id TEXT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    published_at TEXT,
                    fetched_at TEXT,
                    raw_summary TEXT,
                    full_text TEXT,
                    tags_json TEXT,
                    target_role TEXT,
                    impact_score REAL,
                    impact_rationale TEXT,
                    action_items_json TEXT,
                    entities_json TEXT,
                    cluster_id TEXT,
                    confidence REAL,
                    discussion_context TEXT,
                    content_profile TEXT
                );
                """
            )
            # Idempotent migration for existing databases
            cursor = conn.execute("PRAGMA table_info(items);")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "discussion_context" not in existing_cols:
                conn.execute("ALTER TABLE items ADD COLUMN discussion_context TEXT;")
            if "content_profile" not in existing_cols:
                conn.execute("ALTER TABLE items ADD COLUMN content_profile TEXT;")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_source_id ON items(source_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_impact_score ON items(impact_score);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_fetched_at ON items(fetched_at);"
            )

    def upsert_items(self, items: Iterable[Dict[str, Any]]) -> int:
        count = 0
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA busy_timeout = 5000;")
            for item in items:
                self._upsert_one(conn, item)
                count += 1
        return count

    def fetch_recent_titles(self, hours: int) -> List[str]:
        if hours <= 0:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA busy_timeout = 5000;")
            rows = conn.execute(
                "SELECT title FROM items WHERE title IS NOT NULL AND fetched_at >= ?",
                (cutoff.isoformat(),),
            ).fetchall()
        return [row[0] for row in rows if row and row[0]]

    @staticmethod
    def _to_json(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=True)

    def _upsert_one(self, conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO items (
                source_id, item_id, url, title, published_at, fetched_at,
                raw_summary, full_text, tags_json, target_role, impact_score,
                impact_rationale, action_items_json, entities_json, cluster_id,
                confidence, discussion_context, content_profile
            ) VALUES (
                :source_id, :item_id, :url, :title, :published_at, :fetched_at,
                :raw_summary, :full_text, :tags_json, :target_role, :impact_score,
                :impact_rationale, :action_items_json, :entities_json, :cluster_id,
                :confidence, :discussion_context, :content_profile
            )
            ON CONFLICT(url) DO UPDATE SET
                source_id=COALESCE(excluded.source_id, items.source_id),
                item_id=COALESCE(excluded.item_id, items.item_id),
                title=COALESCE(excluded.title, items.title),
                published_at=COALESCE(excluded.published_at, items.published_at),
                fetched_at=COALESCE(excluded.fetched_at, items.fetched_at),
                raw_summary=COALESCE(excluded.raw_summary, items.raw_summary),
                full_text=COALESCE(excluded.full_text, items.full_text),
                tags_json=COALESCE(excluded.tags_json, items.tags_json),
                target_role=COALESCE(excluded.target_role, items.target_role),
                impact_score=COALESCE(excluded.impact_score, items.impact_score),
                impact_rationale=COALESCE(excluded.impact_rationale, items.impact_rationale),
                action_items_json=COALESCE(excluded.action_items_json, items.action_items_json),
                entities_json=COALESCE(excluded.entities_json, items.entities_json),
                cluster_id=COALESCE(excluded.cluster_id, items.cluster_id),
                confidence=COALESCE(excluded.confidence, items.confidence),
                discussion_context=COALESCE(excluded.discussion_context, items.discussion_context),
                content_profile=COALESCE(excluded.content_profile, items.content_profile);
            """,
            {
                "source_id": item.get("source_id"),
                "item_id": item.get("item_id"),
                "url": item.get("url"),
                "title": item.get("title"),
                "published_at": item.get("published_at"),
                "fetched_at": item.get("fetched_at"),
                "raw_summary": item.get("raw_summary"),
                "full_text": item.get("full_text"),
                "tags_json": self._to_json(item.get("tags")),
                "target_role": item.get("target_role"),
                "impact_score": item.get("impact_score"),
                "impact_rationale": item.get("impact_rationale"),
                "action_items_json": self._to_json(item.get("action_items")),
                "entities_json": self._to_json(item.get("entities")),
                "cluster_id": item.get("cluster_id"),
                "confidence": item.get("confidence"),
                "discussion_context": item.get("discussion_context"),
                "content_profile": item.get("content_profile"),
            },
        )
