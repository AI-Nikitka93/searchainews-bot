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


if __name__ == "__main__":
    unittest.main()
