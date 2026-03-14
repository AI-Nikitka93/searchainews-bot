import argparse
import html
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import feedparser
import requests
import yaml
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from storage import SQLiteStorage
from bs4 import BeautifulSoup


LOG = logging.getLogger("scraper")


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_session(config: Dict[str, Any]) -> requests.Session:
    http_cfg = config.get("http", {})
    retries_total = int(http_cfg.get("retries_total", 5))
    backoff_factor = float(http_cfg.get("backoff_factor", 1.5))
    status_forcelist = http_cfg.get("status_forcelist", [429, 500, 502, 503, 504])

    retry = Retry(
        total=retries_total,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    user_agent = http_cfg.get("user_agent")
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    session.headers.update(headers)
    return session


def jitter_sleep(min_max: List[float]) -> None:
    time.sleep(random.uniform(min_max[0], min_max[1]))


def fetch_url(session: requests.Session, url: str, timeout: int, jitter: List[float]) -> str:
    jitter_sleep(jitter)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_url_with_jina_fallback(
    session: requests.Session,
    config: Dict[str, Any],
    source_cfg: Dict[str, Any],
    url: str,
    timeout: int,
    jitter: List[float],
) -> str:
    try:
        return fetch_url(session, url, timeout=timeout, jitter=jitter)
    except requests.RequestException as exc:
        if not source_cfg.get("force_jina", False):
            raise exc
        endpoint = config.get("jina_reader", {}).get("endpoint_prefix", "https://r.jina.ai/")
        jina_url = f"{endpoint}{url}"
        LOG.warning("Primary fetch failed, trying jina: %s", exc)
        return fetch_url(session, jina_url, timeout=timeout, jitter=jitter)


def normalize_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def html_to_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def extract_updated_datetime(text: str) -> Optional[str]:
    patterns = [
        r"Updated:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"Updated\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"Last updated:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_datetime(match.group(1))
    return None


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def should_enrich(url: str, config: Dict[str, Any], source_cfg: Dict[str, Any]) -> bool:
    if not url:
        return False
    if not source_cfg.get("enable_jina", False):
        return False
    if not config.get("jina_reader", {}).get("enabled", False):
        return False
    excluded = config.get("jina_reader", {}).get("exclude_domains", [])
    for domain in excluded:
        if domain.lower() in url.lower():
            return False
    return True


def fetch_full_text(session: requests.Session, config: Dict[str, Any], url: str) -> Optional[str]:
    endpoint = config.get("jina_reader", {}).get("endpoint_prefix", "https://r.jina.ai/")
    if not url.startswith("http"):
        return None
    target = f"{endpoint}{url}"
    try:
        text = fetch_url(
            session,
            target,
            timeout=int(config.get("http", {}).get("timeout_seconds", 25)),
            jitter=config.get("http", {}).get("jitter_seconds", [1.0, 3.0]),
        )
        return text.strip() or None
    except requests.RequestException as exc:
        LOG.warning("jina fetch failed: %s", exc)
        return None


class RSSAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any]):
        self.session = session
        self.config = config

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = source_cfg["url"]
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]

        raw = fetch_url(self.session, url, timeout=timeout, jitter=jitter)
        parsed = feedparser.parse(raw)
        items = []
        max_items = int(source_cfg.get("max_items", 10))
        for entry in parsed.entries[:max_items]:
            link = entry.get("link")
            published = entry.get("published") or entry.get("updated")
            content_value = None
            content_field = entry.get("content")
            if isinstance(content_field, list) and content_field:
                parts = []
                for block in content_field:
                    value = html_to_text(block.get("value") or "")
                    if value:
                        parts.append(value)
                content_value = "\n\n".join(parts).strip() if parts else None
            elif isinstance(content_field, dict):
                content_value = html_to_text(content_field.get("value") or "")
            item = {
                "source_id": source_cfg["id"],
                "item_id": entry.get("id") or entry.get("guid"),
                "url": link,
                "title": entry.get("title"),
                "published_at": normalize_datetime(published),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_summary": html_to_text(entry.get("summary")),
                "full_text": content_value or None,
                "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
                "target_role": None,
                "impact_score": None,
                "impact_rationale": None,
                "action_items": None,
                "entities": None,
                "cluster_id": None,
                "confidence": None,
            }
            items.append(item)
        return items


class HackerNewsAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any]):
        self.session = session
        self.config = config

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        base = source_cfg["url"].rstrip("/") + "/"
        endpoint = source_cfg.get("endpoint", "topstories")
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]

        ids_url = f"{base}{endpoint}.json"
        ids_text = fetch_url(self.session, ids_url, timeout=timeout, jitter=jitter)
        ids = json.loads(ids_text)

        max_items = int(source_cfg.get("max_items", 10))
        items = []
        for item_id in ids[:max_items]:
            item_url = f"{base}item/{item_id}.json"
            item_text = fetch_url(self.session, item_url, timeout=timeout, jitter=jitter)
            data = json.loads(item_text)
            if not data:
                continue
            url = data.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            published_at = datetime.fromtimestamp(int(data.get("time", 0)), tz=timezone.utc).isoformat()
            items.append(
                {
                    "source_id": source_cfg["id"],
                    "item_id": str(item_id),
                    "url": url,
                    "title": data.get("title"),
                    "published_at": published_at,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "raw_summary": html_to_text(data.get("text")),
                    "full_text": None,
                    "tags": None,
                    "target_role": None,
                    "impact_score": None,
                    "impact_rationale": None,
                    "action_items": None,
                    "entities": None,
                    "cluster_id": None,
                    "confidence": None,
                }
            )
        return items


class ReleaseNotesAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any]):
        self.session = session
        self.config = config

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = source_cfg["url"]
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]

        raw_html = fetch_url_with_jina_fallback(
            self.session, self.config, source_cfg, url, timeout=timeout, jitter=jitter
        )
        soup = BeautifulSoup(raw_html, "html.parser")
        container = soup.find("article") or soup.body or soup
        heading_tags = source_cfg.get("heading_tags", ["h2", "h3"])

        all_text = soup.get_text(" ", strip=True)
        page_updated = extract_updated_datetime(all_text)

        headings = container.find_all(heading_tags)
        max_items = int(source_cfg.get("max_items", 10))
        items: List[Dict[str, Any]] = []

        if not headings:
            text = html_to_text(str(container))
            items.append(
                self._build_item(
                    source_cfg=source_cfg,
                    title=soup.title.string.strip() if soup.title else source_cfg.get("name"),
                    url=url,
                    published_at=page_updated,
                    body=text,
                )
            )
            return items[:max_items]

        for heading in headings[:max_items]:
            title = heading.get_text(strip=True)
            if not title:
                continue
            section_text = self._collect_section_text(heading, heading_tags)
            published_at = self._try_parse_heading_date(title) or page_updated
            item_url = f"{url}#{slugify(title)}"
            items.append(
                self._build_item(
                    source_cfg=source_cfg,
                    title=title,
                    url=item_url,
                    published_at=published_at,
                    body=section_text,
                )
            )

        return items

    @staticmethod
    def _collect_section_text(heading, heading_tags: List[str]) -> Optional[str]:
        texts: List[str] = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in heading_tags:
                break
            if getattr(sibling, "get_text", None):
                text = sibling.get_text(" ", strip=True)
                if text:
                    texts.append(text)
        combined = " ".join(texts).strip()
        return combined or None

    @staticmethod
    def _try_parse_heading_date(title: str) -> Optional[str]:
        month_pattern = (
            r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|"
            r"jul(y)?|aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|"
            r"dec(ember)?)"
        )
        if not re.search(r"\b(19|20)\d{2}\b", title, re.IGNORECASE) and not re.search(
            month_pattern, title, re.IGNORECASE
        ):
            return None
        try:
            dt = date_parser.parse(title, fuzzy=True)
            if not dt:
                return None
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _build_item(
        source_cfg: Dict[str, Any],
        title: Optional[str],
        url: str,
        published_at: Optional[str],
        body: Optional[str],
    ) -> Dict[str, Any]:
        summary = None
        if body:
            summary = body[:300]
        return {
            "source_id": source_cfg["id"],
            "item_id": slugify(title or url),
            "url": url,
            "title": title,
            "published_at": published_at,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "raw_summary": summary,
            "full_text": body,
            "tags": None,
            "target_role": None,
            "impact_score": None,
            "impact_rationale": None,
            "action_items": None,
            "entities": None,
            "cluster_id": None,
            "confidence": None,
        }


def build_adapters(session: requests.Session, config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rss": RSSAdapter(session, config),
        "hackernews": HackerNewsAdapter(session, config),
        "release_notes": ReleaseNotesAdapter(session, config),
    }


def run_scraper(config_path: str, smoke_test: bool = False) -> int:
    config = load_config(config_path)
    session = build_session(config)
    storage = SQLiteStorage(config["db_path"])
    adapters = build_adapters(session, config)

    source_pause = config["http"]["source_pause_seconds"]
    all_items: List[Dict[str, Any]] = []

    sources = config.get("sources", [])
    if smoke_test:
        preferred_ids = {"techcrunch_feed", "wired_ai", "mit_news_ai", "nvidia_blog"}
        preferred = [s for s in sources if s.get("id") in preferred_ids]
        sources = (preferred or sources)[:2]

    for source_cfg in sources:
        src_type = source_cfg.get("type")
        adapter = adapters.get(src_type)
        if not adapter:
            LOG.warning("No adapter for source type: %s", src_type)
            continue
        LOG.info("Fetching source: %s", source_cfg.get("name"))
        try:
            items = adapter.fetch_items(source_cfg)
        except requests.RequestException as exc:
            LOG.warning("Fetch failed for %s: %s", source_cfg.get("id"), exc)
            continue

        for item in items:
            if should_enrich(item.get("url"), config, source_cfg):
                enriched = fetch_full_text(session, config, item["url"])
                if enriched:
                    item["full_text"] = enriched
        all_items.extend(items)
        jitter_sleep(source_pause)

    saved = storage.upsert_items(all_items)
    LOG.info("Saved %s items", saved)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="News scraper")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run limited sources/items for smoke test",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    run_scraper(args.config, smoke_test=args.smoke_test)


if __name__ == "__main__":
    main()
