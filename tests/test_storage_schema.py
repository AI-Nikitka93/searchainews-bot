import os
import tempfile
import unittest
from storage import SQLiteStorage


class TestStorageSchema(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.db_path = self.temp_file.name

    def tearDown(self):
        import gc
        gc.collect()
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except OSError:
            pass

    def test_t001_schema_has_discussion_and_profile_columns(self):
        import sqlite3
        storage = SQLiteStorage(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
        self.assertIn("discussion_context", cols)
        self.assertIn("content_profile", cols)

    def test_t002_upsert_persists_and_coalesce_guards(self):
        import sqlite3
        storage = SQLiteStorage(self.db_path)
        item = {
            "source_id": "test_src",
            "url": "https://example.com/test1",
            "title": "Title 1",
            "discussion_context": "Sample discussion",
            "content_profile": "model_release",
        }
        storage.upsert_items([item])

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT discussion_context, content_profile FROM items WHERE url='https://example.com/test1'"
            ).fetchone()
        self.assertEqual(row, ("Sample discussion", "model_release"))

        # Re-upsert with None values: COALESCE should preserve existing values
        item_update = {
            "source_id": "test_src",
            "url": "https://example.com/test1",
            "title": "Title 1 Updated",
            "discussion_context": None,
            "content_profile": None,
        }
        storage.upsert_items([item_update])

        with sqlite3.connect(self.db_path) as conn:
            row2 = conn.execute(
                "SELECT discussion_context, content_profile FROM items WHERE url='https://example.com/test1'"
            ).fetchone()
        self.assertEqual(row2, ("Sample discussion", "model_release"))

    def test_t003_upsert_preserves_impact_score_and_role(self):
        import sqlite3
        storage = SQLiteStorage(self.db_path)
        item = {
            "source_id": "test_src",
            "url": "https://example.com/scored",
            "title": "Scored Article",
            "impact_score": 5.0,
            "target_role": "developer",
            "impact_rationale": "Major foundation model release",
        }
        storage.upsert_items([item])

        # Verify initial score
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT impact_score, target_role, impact_rationale FROM items WHERE url='https://example.com/scored'"
            ).fetchone()
        self.assertEqual(row, (5.0, "developer", "Major foundation model release"))

        # Re-upsert without impact_score (e.g. re-scraped by scraper.py)
        re_scraped = {
            "source_id": "test_src",
            "url": "https://example.com/scored",
            "title": "Scored Article (Updated)",
        }
        storage.upsert_items([re_scraped])

        # Verify impact_score and target_role are preserved
        with sqlite3.connect(self.db_path) as conn:
            row2 = conn.execute(
                "SELECT impact_score, target_role, impact_rationale FROM items WHERE url='https://example.com/scored'"
            ).fetchone()
        self.assertEqual(row2, (5.0, "developer", "Major foundation model release"))


if __name__ == "__main__":
    unittest.main()
