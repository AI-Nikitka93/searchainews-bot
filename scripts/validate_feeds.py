import argparse
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


DEFAULT_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def build_headers(config: Dict[str, Any]) -> Dict[str, str]:
    user_agent = config.get("http", {}).get("user_agent") or "Mozilla/5.0"
    return {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def validate_source(source: Dict[str, Any], default_headers: Dict[str, str], default_timeout: int) -> Tuple[bool, int, str]:
    candidate_urls = [source["url"]]
    if source.get("fallback_url"):
        candidate_urls.append(source["fallback_url"])
    for fb in source.get("fallback_urls", []):
        if fb and fb not in candidate_urls:
            candidate_urls.append(fb)

    timeout = int(source.get("timeout_seconds") or default_timeout)
    req_headers = dict(default_headers)
    if source.get("use_browser_headers"):
        req_headers.update(DEFAULT_BROWSER_HEADERS)
    if source.get("headers"):
        req_headers.update(source.get("headers"))
    if source.get("user_agent"):
        req_headers["User-Agent"] = source["user_agent"]

    last_detail = "no url"
    for candidate_url in candidate_urls:
        try:
            resp = requests.get(candidate_url, headers=req_headers, timeout=timeout)
            if resp.status_code == 403 and req_headers.get("User-Agent") != DEFAULT_BROWSER_HEADERS["User-Agent"]:
                retry_headers = dict(DEFAULT_BROWSER_HEADERS)
                if source.get("headers"):
                    retry_headers.update(source.get("headers"))
                resp = requests.get(candidate_url, headers=retry_headers, timeout=timeout)
            if resp.status_code >= 400:
                last_detail = f"HTTP {resp.status_code}"
                continue
            trimmed = resp.text.strip()
            if (trimmed.startswith("[") or trimmed.startswith("{")) and not trimmed.startswith("<"):
                import json
                try:
                    data = json.loads(trimmed)
                    count = len(data) if isinstance(data, list) else len(data.get("posts", []))
                    if count > 0:
                        return True, count, "ok (json)"
                except Exception:
                    pass
            parsed = feedparser.parse(resp.text)
            entries = len(parsed.entries)
            if entries == 0:
                last_detail = "no entries"
                continue
            return True, entries, "ok"
        except Exception as e:
            last_detail = f"NetworkError: {type(e).__name__}"
            continue
    return False, 0, last_detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RSS feeds in config.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source-id", default="")
    args = parser.parse_args()

    config = load_config(args.config)
    headers = build_headers(config)
    timeout = int(config.get("http", {}).get("timeout_seconds", 25))

    import time
    sources: List[Dict[str, Any]] = [
        s for s in config.get("sources", []) if s.get("type") == "rss" and s.get("enabled", True)
    ]
    allow_empty_ids = set(config.get("validate_feeds_allow_empty_ids", []))
    if args.source_id:
        requested = {part.strip() for part in args.source_id.split(",") if part.strip()}
        sources = [s for s in sources if s.get("id") in requested]
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
        time.sleep(1.5)
        ok, entries, detail = validate_source(source, headers, timeout)
        soft_ok = not ok and detail == "no entries" and source_id in allow_empty_ids
        status = "OK" if ok or soft_ok else "FAIL"
        print(f"{source_id}: {status} entries={entries} {detail}")
        if not ok and not soft_ok:
            failures += 1

    if failures:
        print(f"Feed validation failures: {failures}")
        return 1
    print("Feed validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
