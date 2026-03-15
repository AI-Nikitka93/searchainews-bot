import argparse
import os
from typing import Dict, Any, List, Tuple

import feedparser
import requests
import yaml


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_headers(config: Dict[str, Any]) -> Dict[str, str]:
    user_agent = config.get("http", {}).get("user_agent") or "Mozilla/5.0"
    return {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def validate_feed(url: str, headers: Dict[str, str], timeout: int) -> Tuple[bool, int, str]:
    resp = requests.get(url, headers=headers, timeout=timeout)
    status = resp.status_code
    if status >= 400:
        return False, 0, f"HTTP {status}"
    parsed = feedparser.parse(resp.text)
    entries = len(parsed.entries)
    if entries == 0:
        return False, 0, "no entries"
    return True, entries, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RSS feeds in config.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    config = load_config(args.config)
    headers = build_headers(config)
    timeout = int(config.get("http", {}).get("timeout_seconds", 25))

    sources: List[Dict[str, Any]] = [
        s for s in config.get("sources", []) if s.get("type") == "rss"
    ]
    sources = sources[: max(args.limit, 0)]
    if not sources:
        print("No RSS sources found.")
        return 1

    failures = 0
    for source in sources:
        source_id = source.get("id")
        url = source.get("url")
        if not url:
            print(f"{source_id}: missing url")
            failures += 1
            continue
        ok, entries, detail = validate_feed(url, headers, timeout)
        status = "OK" if ok else "FAIL"
        print(f"{source_id}: {status} entries={entries} {detail}")
        if not ok:
            failures += 1

    if failures:
        print(f"Feed validation failures: {failures}")
        return 1
    print("Feed validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
