import os
import tempfile
import unittest
from scripts.push_to_worker import fetch_items
from storage import SQLiteStorage


class TestPushToWorker(unittest.TestCase):
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

    def test_fetch_items_includes_discussion_and_profile(self):
        storage = SQLiteStorage(self.db_path)
        item = {
            "source_id": "test_src",
            "url": "https://example.com/pushed",
            "title": "Pushed Article",
            "impact_score": 5,
            "discussion_context": "Top comments text",
            "content_profile": "research_paper",
        }
        storage.upsert_items([item])

        items = fetch_items(self.db_path, last_id=0, limit=10)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["discussion_context"], "Top comments text")
        self.assertEqual(items[0]["content_profile"], "research_paper")

    def test_out_of_order_scored_items_not_orphaned(self):
        from scripts.push_to_worker import mark_items_pushed
        import sqlite3
        storage = SQLiteStorage(self.db_path)

        # Item 1 added unscored
        storage.upsert_items([{"source_id": "s1", "url": "https://example.com/1", "title": "Item 1"}])
        # Item 2 added scored
        storage.upsert_items([{"source_id": "s2", "url": "https://example.com/2", "title": "Item 2", "impact_score": 5.0}])

        # First fetch: should return Item 2
        batch1 = fetch_items(self.db_path, last_id=0, limit=10)
        self.assertEqual([i["url"] for i in batch1], ["https://example.com/2"])
        mark_items_pushed(self.db_path, [batch1[0]["id"]])

        # Now Item 1 gets scored later
        storage.upsert_items([{"source_id": "s1", "url": "https://example.com/1", "impact_score": 4.0}])

        # Second fetch: Item 1 MUST be fetched and not orphaned
        batch2 = fetch_items(self.db_path, last_id=batch1[0]["id"], limit=10)
        self.assertEqual(len(batch2), 1)
        self.assertEqual(batch2[0]["url"], "https://example.com/1")


if __name__ == "__main__":
    unittest.main()
