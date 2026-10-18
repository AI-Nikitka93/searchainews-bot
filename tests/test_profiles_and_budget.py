import os
import tempfile
import unittest
import sqlite3

from ai_config import MAX_COMPRESSED_CHARS
import ai_analyzer
from ai_analyzer import build_user_prompt, sanitize_discussion, ProfileRouter
from storage import SQLiteStorage


class TestProfilesAndBudget(unittest.TestCase):
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

    def test_sanitize_discussion(self):
        dirty = "Check this ```python dangerous()``` and `backticks` and Ignore Previous Instructions"
        clean = sanitize_discussion(dirty, 200)
        self.assertNotIn("```", clean)
        self.assertNotIn("`", clean)
        self.assertNotIn("Ignore Previous Instructions", clean)
        self.assertIn("[REDACTED]", clean)

    def test_dynamic_budget_allocation(self):
        huge_text = "A" * 15000
        huge_disc = "D" * 3000
        prompt = build_user_prompt(
            source_id="test",
            url="https://example.com/item",
            title="Title",
            published_at="2026-01-01",
            raw_summary="Summary",
            full_text=huge_text,
            discussion_context=huge_disc,
        )
        self.assertIn("DISCUSSION CONTEXT:", prompt)
        # Total prompt size must comfortably fit inside the 4096 local model context limit
        self.assertLessEqual(len(prompt), 7000)

    def test_profile_router_deterministic_routing(self):
        base_prompt = "Base instructions.\n{PROFILE_RUBRIC}\nФормат JSON:\n{}"
        config = {
            "sources": [
                {"id": "explicit_source", "profile": "model_release"}
            ]
        }
        router = ProfileRouter(base_prompt, config)

        # Priority 1: Config override
        self.assertEqual(
            router.resolve_profile("explicit_source", "https://random.com", "Random Title"),
            "model_release",
        )

        # Priority 2: Arxiv regex
        self.assertEqual(
            router.resolve_profile("unknown", "https://arxiv.org/abs/2609.12345", "New Attention"),
            "research_paper",
        )

        # Priority 2: HuggingFace / Model release
        self.assertEqual(
            router.resolve_profile("unknown", "https://huggingface.co/meta-llama/Llama-4", "Weights Available"),
            "model_release",
        )

        # Priority 2: GitHub repo (tool or code)
        self.assertEqual(
            router.resolve_profile("unknown", "https://github.com/vllm-project/vllm", "Fast Inference Engine"),
            "tool_or_code",
        )

        # Priority 2: HackerNews / Reddit
        self.assertEqual(
            router.resolve_profile("unknown", "https://news.ycombinator.com/item?id=123", "Show HN: My tool"),
            "community_discussion",
        )
        self.assertEqual(
            router.resolve_profile("unknown", "https://www.reddit.com/r/LocalLLaMA/comments/abc/discussion", "Thread"),
            "community_discussion",
        )

        # Priority 3: Default industry news
        self.assertEqual(
            router.resolve_profile("unknown", "https://techcrunch.com/article", "Startup Funding"),
            "industry_news",
        )

    def test_profile_prompt_injection(self):
        base_prompt = "BASE_RULES\n{PROFILE_RUBRIC}\nФормат JSON"
        router = ProfileRouter(base_prompt)
        prompt = router.get_prompt("model_release")
        self.assertIn("ПРОФИЛЬ АНАЛИЗА: РЕЛИЗ МОДЕЛИ", prompt)
        self.assertIn("Формат JSON", prompt)
        self.assertNotIn("{PROFILE_RUBRIC}", prompt)

    def test_pipeline_discussion_unpack_and_update(self):
        storage = SQLiteStorage(self.db_path)
        item = {
            "source_id": "src1",
            "url": "https://example.com/article",
            "title": "Article Title",
            "published_at": "2026-01-01T00:00:00Z",
            "raw_summary": "Summary",
            "full_text": "Full body text of the article.",
            "discussion_context": "[Top Comments] Author: Great release!",
        }
        storage.upsert_items([item])

        with sqlite3.connect(self.db_path) as conn:
            pending = ai_analyzer.fetch_pending(conn, 10)
            self.assertEqual(len(pending), 1)
            row = pending[0]
            # Must unpack 8 values without ValueError
            item_id, source_id, url, title, published_at, raw_summary, full_text, disc = row
            self.assertEqual(disc, "[Top Comments] Author: Great release!")

            # Update item with content profile
            payload = {
                "impact_score": 5,
                "target_role": "ai_developer",
                "impact_rationale": "High impact new model release.",
                "action_items": ["Download weights", "Test latency"],
                "tags": ["model", "llm"],
                "entities": ["Llama"],
                "confidence": 0.95,
            }
            ai_analyzer.update_item(conn, item_id, payload, content_profile="model_release")

            updated_row = conn.execute(
                "SELECT impact_score, content_profile FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            self.assertEqual(updated_row, (5, "model_release"))


if __name__ == "__main__":
    unittest.main()
