import unittest
from unittest.mock import MagicMock
import requests

from scraper import RSSAdapter, normalize_url, DEFAULT_BROWSER_HEADERS, DEFAULT_BROWSER_USER_AGENT


class TestFeedResilience(unittest.TestCase):
    def test_normalize_url_collapses_double_slashes(self):
        url = "https://bairblog.github.io//2026/07/29/cuda-to-mlx-k-search/"
        normalized = normalize_url(url)
        self.assertEqual(normalized, "https://bairblog.github.io/2026/07/29/cuda-to-mlx-k-search")

    def test_rss_adapter_falls_back_on_connection_error(self):
        session = MagicMock(spec=requests.Session)
        state = {}
        config = {
            "http": {"timeout_seconds": 25, "jitter_seconds": [0.0, 0.0]},
            "freshness_max_days": 365,
            "min_title_chars": 20,
            "min_summary_chars": 30,
        }
        adapter = RSSAdapter(session, config, state)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>BAIR Blog Mirror</title>
                <link>https://bairblog.github.io/</link>
                <item>
                    <title>Mirror Entry 1: Breakthrough in Kernel Optimization for Apple Silicon</title>
                    <link>https://bairblog.github.io/2026/07/29/entry1</link>
                    <pubDate>Wed, 29 Jul 2026 02:00:00 -0700</pubDate>
                    <description>Detailed technical summary of kernel optimization benchmarks and experimental evaluation results.</description>
                </item>
            </channel>
        </rss>"""

        def mock_get(url, timeout=25, headers=None):
            if "bair.berkeley.edu" in url:
                raise requests.exceptions.ConnectionError("Connection timeout / SSL error")
            resp = MagicMock()
            resp.status_code = 200
            resp.text = xml_content
            resp.headers = {"ETag": '"mirror-etag"'}
            return resp

        session.get.side_effect = mock_get

        source_cfg = {
            "id": "bair_blog",
            "name": "Berkeley BAIR Blog",
            "type": "rss",
            "url": "https://bair.berkeley.edu/blog/feed.xml",
            "fallback_url": "https://bairblog.github.io/feed.xml",
            "max_items": 5,
        }

        items = adapter.fetch_items(source_cfg)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Mirror Entry 1: Breakthrough in Kernel Optimization for Apple Silicon")
        self.assertEqual(items[0]["source_id"], "bair_blog")
        self.assertEqual(state["bair_blog"]["etag"], '"mirror-etag"')

    def test_rss_adapter_retries_with_browser_headers_on_403(self):
        session = MagicMock(spec=requests.Session)
        state = {}
        config = {
            "http": {"timeout_seconds": 25, "jitter_seconds": [0.0, 0.0]},
            "freshness_max_days": 365,
            "min_title_chars": 20,
            "min_summary_chars": 30,
        }
        adapter = RSSAdapter(session, config, state)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Turing Post</title>
                <link>https://turingpost.substack.com</link>
                <item>
                    <title>Substack Post 1: AI Is Learning What to Remember and Predict</title>
                    <link>https://turingpost.substack.com/p/post-1</link>
                    <pubDate>Mon, 15 Jul 2026 12:00:00 GMT</pubDate>
                    <description>In this deep dive we explore memory mechanisms, predictive models, and self-improving agents.</description>
                </item>
            </channel>
        </rss>"""

        call_headers = []

        def mock_get(url, timeout=25, headers=None):
            call_headers.append(dict(headers or {}))
            resp = MagicMock()
            if headers and headers.get("User-Agent") == DEFAULT_BROWSER_USER_AGENT:
                resp.status_code = 200
                resp.text = xml_content
                resp.headers = {}
                return resp
            else:
                resp.status_code = 403
                return resp

        session.get.side_effect = mock_get

        source_cfg = {
            "id": "turing_post",
            "name": "Turing Post",
            "type": "rss",
            "url": "https://turingpost.substack.com/feed",
            "max_items": 5,
        }

        items = adapter.fetch_items(source_cfg)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Substack Post 1: AI Is Learning What to Remember and Predict")
        self.assertEqual(len(call_headers), 2)
        self.assertEqual(call_headers[1]["User-Agent"], DEFAULT_BROWSER_USER_AGENT)

    def test_rss_adapter_parses_json_api_fallback(self):
        session = MagicMock(spec=requests.Session)
        state = {}
        config = {
            "http": {"timeout_seconds": 25, "jitter_seconds": [0.0, 0.0]},
            "freshness_max_days": 365,
            "min_title_chars": 20,
            "min_summary_chars": 30,
        }
        adapter = RSSAdapter(session, config, state)

        json_content = """[
            {
                "id": 999,
                "title": "Substack JSON Post: Comprehensive Survey of Autonomous Reasoning Systems",
                "canonical_url": "https://turingpost.substack.com/p/json-post",
                "post_date": "2026-07-20T10:00:00Z",
                "subtitle": "Subtitle summary explaining the architecture of autonomous reasoning systems in production.",
                "body_html": "<p>Full content from JSON API with extensive technical details and diagrams.</p>"
            }
        ]"""

        def mock_get(url, timeout=25, headers=None):
            if "feed" in url:
                raise requests.exceptions.HTTPError("403 Forbidden")
            resp = MagicMock()
            resp.status_code = 200
            resp.text = json_content
            resp.headers = {"Content-Type": "application/json"}
            return resp

        session.get.side_effect = mock_get

        source_cfg = {
            "id": "turing_post",
            "name": "Turing Post",
            "type": "rss",
            "url": "https://turingpost.substack.com/feed",
            "fallback_url": "https://turingpost.substack.com/api/v1/posts?limit=12",
            "max_items": 5,
        }

        items = adapter.fetch_items(source_cfg)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Substack JSON Post: Comprehensive Survey of Autonomous Reasoning Systems")
        self.assertEqual(items[0]["url"], "https://turingpost.substack.com/p/json-post")
        self.assertIn("Subtitle summary explaining the architecture", items[0]["raw_summary"])


if __name__ == "__main__":
    unittest.main()
