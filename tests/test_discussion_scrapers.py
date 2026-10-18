import unittest
from unittest.mock import MagicMock
import requests

from scraper import fetch_hn_comments, fetch_reddit_comments


class TestDiscussionScrapers(unittest.TestCase):
    def test_fetch_hn_comments_filters_dead_and_deleted(self):
        session = MagicMock(spec=requests.Session)

        def mock_get(url, timeout=3.0):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "101.json" in url:
                mock_resp.json.return_value = {
                    "by": "alice",
                    "text": "This is a great benchmark for llama models and quantization.",
                }
            elif "102.json" in url:
                mock_resp.json.return_value = {"dead": True, "by": "spammer", "text": "spam"}
            elif "103.json" in url:
                mock_resp.json.return_value = {"deleted": True, "by": "deleted", "text": "deleted"}
            elif "104.json" in url:
                mock_resp.json.return_value = {
                    "by": "bob",
                    "text": "Tested on RTX 4090 and inference runs at 80 tokens per second.",
                }
            else:
                mock_resp.status_code = 404
                mock_resp.json.return_value = None
            return mock_resp

        session.get.side_effect = mock_get
        result = fetch_hn_comments(session, "https://hacker-news.firebaseio.com/v0/", [101, 102, 103, 104], max_comments=3)
        self.assertIsNotNone(result)
        self.assertIn("[HackerNews Top Comments]", result)
        self.assertIn("alice", result)
        self.assertIn("bob", result)
        self.assertNotIn("spammer", result)
        self.assertNotIn("deleted", result)

    def test_fetch_hn_comments_handles_network_failure(self):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.RequestException("Network timeout")
        result = fetch_hn_comments(session, "https://hacker-news.firebaseio.com/v0/", [101, 102])
        self.assertIsNone(result)

    def test_fetch_reddit_comments_filters_automod_and_stickied(self):
        session = MagicMock(spec=requests.Session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"data": {"children": []}},  # post listing
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "author": "AutoModerator",
                                "body": "Please read our community rules before posting.",
                                "stickied": True,
                                "score": 1,
                            }
                        },
                        {
                            "data": {
                                "author": "ml_engineer",
                                "body": "The fp8 weights fit into 16GB VRAM cleanly with minimal loss.",
                                "stickied": False,
                                "score": 52,
                            }
                        },
                        {
                            "data": {
                                "author": "[deleted]",
                                "body": "[removed]",
                                "stickied": False,
                                "score": 0,
                            }
                        },
                        {
                            "data": {
                                "author": "cuda_guru",
                                "body": "Kernel compilation requires CUDA 12.4+ and triton 3.0.",
                                "stickied": False,
                                "score": 28,
                            }
                        },
                    ]
                }
            },
        ]
        session.get.return_value = mock_resp

        url = "https://www.reddit.com/r/MachineLearning/comments/1abcde/new_model_released/"
        result = fetch_reddit_comments(session, url, max_comments=3)
        self.assertIsNotNone(result)
        self.assertIn("[Reddit Top Comments]", result)
        self.assertIn("ml_engineer (score: 52)", result)
        self.assertIn("cuda_guru (score: 28)", result)
        self.assertNotIn("AutoModerator", result)
        self.assertNotIn("[deleted]", result)

    def test_fetch_reddit_comments_handles_rate_limits(self):
        session = MagicMock(spec=requests.Session)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        session.get.return_value = mock_resp

        url = "https://www.reddit.com/r/LocalLLaMA/comments/2xyz/quantization/"
        # 429 should return None gracefully without raising exceptions
        result = fetch_reddit_comments(session, url)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
