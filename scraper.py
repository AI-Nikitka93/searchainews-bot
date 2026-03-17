import argparse
import html
import json
import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import feedparser
import requests
import yaml
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from storage import SQLiteStorage
from bs4 import BeautifulSoup


LOG = logging.getLogger("scraper")

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_cid",
    "utm_reader",
    "utm_referrer",
    "ref",
    "source",
    "fbclid",
    "gclid",
    "yclid",
    "mc_cid",
    "mc_eid",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    cleaned = html.unescape(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_item_fields(item: Dict[str, Any]) -> None:
    for key in ("title", "raw_summary", "full_text"):
        if item.get(key):
            item[key] = normalize_text(str(item[key]))


def tokenize_title(title: Optional[str]) -> List[str]:
    if not title:
        return []
    normalized = normalize_title_for_dedupe(title)
    if not normalized:
        return []
    tokens = [token for token in normalized.split(" ") if token and token not in STOPWORDS]
    return tokens


def jaccard(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    set_a = set(a)
    set_b = set(b)
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / max(len(union), 1)


def is_semantic_duplicate(
    tokens: List[str],
    recent_tokens: List[List[str]],
    threshold: float,
    max_compare: int,
) -> bool:
    if not tokens:
        return False
    if max_compare > 0:
        candidates = recent_tokens[-max_compare:]
    else:
        candidates = recent_tokens
    for existing in candidates:
        if jaccard(tokens, existing) >= threshold:
            return True
    return False


def get_state_dir() -> Path:
    base = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / "SearchAInews" / "state"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_source_state() -> Dict[str, Any]:
    path = get_state_dir() / "source_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_source_state(state: Dict[str, Any]) -> None:
    path = get_state_dir() / "source_state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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


def fetch_url(
    session: requests.Session,
    url: str,
    timeout: int,
    jitter: List[float],
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[str, requests.Response]:
    jitter_sleep(jitter)
    resp = session.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp.text, resp


def fetch_url_with_jina_fallback(
    session: requests.Session,
    config: Dict[str, Any],
    source_cfg: Dict[str, Any],
    url: str,
    timeout: int,
    jitter: List[float],
) -> str:
    jina_timeout = int(config.get("http", {}).get("jina_timeout_seconds", timeout))
    if source_cfg.get("jina_only", False):
        endpoint = config.get("jina_reader", {}).get("endpoint_prefix", "https://r.jina.ai/")
        jina_url = f"{endpoint}{url}"
        text, _ = fetch_url(session, jina_url, timeout=jina_timeout, jitter=jitter)
        return text
    try:
        text, _ = fetch_url(session, url, timeout=timeout, jitter=jitter)
        return text
    except requests.RequestException as exc:
        if not source_cfg.get("force_jina", False):
            raise exc
        endpoint = config.get("jina_reader", {}).get("endpoint_prefix", "https://r.jina.ai/")
        jina_url = f"{endpoint}{url}"
        LOG.warning("Primary fetch failed, trying jina: %s", exc)
        try:
            text, _ = fetch_url(session, jina_url, timeout=jina_timeout, jitter=jitter)
            return text
        except requests.RequestException as jina_exc:
            LOG.warning("Jina fetch failed: %s", jina_exc)
            return ""


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


def normalize_datetime_from_entry(entry: Any) -> Optional[str]:
    candidates = [
        entry.get("published"),
        entry.get("updated"),
        entry.get("pubDate"),
        entry.get("dc:date"),
    ]
    for value in candidates:
        parsed = normalize_datetime(value)
        if parsed:
            return parsed
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_struct = entry.get(key)
        if parsed_struct:
            try:
                dt = datetime(*parsed_struct[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                continue
    return None


def normalize_datetime_fuzzy(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = date_parser.parse(value, fuzzy=True)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def extract_date_from_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    patterns = [
        r"\b(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            parsed = normalize_datetime(match.group(0))
            if parsed:
                return parsed
    return None


def html_to_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if not url.startswith("http"):
        return url
    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
    filtered = []
    for key, value in query_pairs:
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_PARAMS:
            continue
        filtered.append((key, value))
    cleaned_query = urlencode(filtered, doseq=True)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            cleaned_query,
            parsed.fragment,
        )
    )


def _keyword_match(term: str, text: str) -> bool:
    term = term.strip().lower()
    if not term:
        return False
    if len(term) <= 3:
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def passes_keyword_filter(
    title: Optional[str],
    summary: Optional[str],
    tags: Optional[List[str]],
    source_cfg: Dict[str, Any],
    config: Dict[str, Any],
) -> bool:
    if not passes_title_filter(title, source_cfg, config):
        return False
    include = source_cfg.get("keywords_include") or config.get("keywords_include") or []
    exclude = source_cfg.get("keywords_exclude") or config.get("keywords_exclude") or []
    if not include and not exclude:
        return True
    parts = [title or "", summary or ""]
    if tags:
        parts.append(" ".join(tags))
    text = " ".join(parts).lower()
    if exclude and any(_keyword_match(term, text) for term in exclude):
        return False
    if include:
        return any(_keyword_match(term, text) for term in include)
    return True


def passes_title_filter(
    title: Optional[str],
    source_cfg: Dict[str, Any],
    config: Dict[str, Any],
) -> bool:
    if not title:
        return True
    patterns = source_cfg.get("title_exclude_regex") or config.get("title_exclude_regex") or []
    for pattern in patterns:
        try:
            if re.search(pattern, title, re.IGNORECASE):
                return False
        except re.error as exc:
            LOG.warning("Invalid title_exclude_regex pattern %s: %s", pattern, exc)
    return True


def passes_content_quality(
    title: Optional[str],
    summary: Optional[str],
    full_text: Optional[str],
    source_cfg: Dict[str, Any],
    config: Dict[str, Any],
) -> bool:
    min_summary = int(source_cfg.get("min_summary_chars", config.get("min_summary_chars", 60)))
    min_full_text = int(source_cfg.get("min_full_text_chars", config.get("min_full_text_chars", 200)))
    min_title = int(source_cfg.get("min_title_chars", config.get("min_title_chars", 30)))
    if full_text and len(full_text.strip()) >= min_full_text:
        return True
    if summary and len(summary.strip()) >= min_summary:
        return True
    if title and len(title.strip()) >= min_title:
        return True
    return False


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


def extract_meta_content(soup: BeautifulSoup, keys: List[str]) -> Optional[str]:
    lowered = {key.lower() for key in keys}
    for meta in soup.find_all("meta"):
        key = meta.get("property") or meta.get("name")
        if key and key.lower() in lowered:
            content = meta.get("content")
            if content:
                return content.strip()
    return None


def extract_article_datetime(soup: BeautifulSoup, fallback_text: Optional[str] = None) -> Optional[str]:
    meta_value = extract_meta_content(
        soup,
        [
            "article:published_time",
            "article:modified_time",
            "published_time",
            "pubdate",
            "date",
            "dc.date",
        ],
    )
    parsed = normalize_datetime(meta_value)
    if parsed:
        return parsed

    time_tag = soup.find("time")
    if time_tag:
        parsed = normalize_datetime(time_tag.get("datetime")) or normalize_datetime_fuzzy(
            time_tag.get_text(" ", strip=True)
        )
        if parsed:
            return parsed

    if fallback_text:
        return extract_date_from_text(fallback_text) or normalize_datetime_fuzzy(fallback_text)
    return None


def extract_article_title(soup: BeautifulSoup, fallback: Optional[str] = None) -> Optional[str]:
    meta_title = extract_meta_content(soup, ["og:title", "twitter:title"])
    if meta_title:
        return re.sub(r"\s+\|\s+[^|]+$", "", meta_title).strip()
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(" ", strip=True)
        if text:
            return text
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(" ", strip=True)
        if text:
            return re.sub(r"\s+\|\s+[^|]+$", "", text).strip()
    return fallback


def extract_article_text(soup: BeautifulSoup) -> Optional[str]:
    container = soup.find("article") or soup.find("main") or soup.body or soup
    if not container:
        return None

    for tag in container.find_all(["script", "style", "noscript", "svg", "form", "button"]):
        tag.decompose()

    text = container.get_text(" ", strip=True)
    return normalize_text(text)


def extract_listing_title(text: str, separator: str = "|", index: int = 0) -> str:
    parts = [part.strip() for part in text.split(separator) if part.strip()]
    if not parts:
        return text.strip()
    if 0 <= index < len(parts):
        return parts[index]
    return parts[0]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def normalize_title_for_dedupe(title: Optional[str]) -> str:
    if not title:
        return ""
    text = title.lower()
    text = re.sub(r"['\"`’]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_dedupe_key(url: Optional[str], title: Optional[str]) -> Optional[str]:
    if not url and not title:
        return None
    host = ""
    if url:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
    normalized_title = normalize_title_for_dedupe(title)
    if normalized_title:
        return f"{host}:{normalized_title}"
    return url


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
        text, _ = fetch_url(
            session,
            target,
            timeout=int(config.get("http", {}).get("jina_timeout_seconds", config.get("http", {}).get("timeout_seconds", 25))),
            jitter=config.get("http", {}).get("jitter_seconds", [1.0, 3.0]),
        )
        return text.strip() or None
    except requests.RequestException as exc:
        LOG.warning("jina fetch failed: %s", exc)
        return None


def is_fresh(published_at: Optional[str], max_age_days: Optional[int]) -> bool:
    if not max_age_days or not published_at:
        return True
    try:
        dt = date_parser.parse(published_at)
    except (ValueError, TypeError):
        return True
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return dt.astimezone(timezone.utc) >= cutoff


def is_disabled(state_entry: Dict[str, Any]) -> bool:
    disabled_until = state_entry.get("disabled_until")
    if not disabled_until:
        return False
    try:
        return datetime.now(timezone.utc) < datetime.fromisoformat(disabled_until)
    except ValueError:
        return False


class RSSAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any], state: Dict[str, Any]):
        self.session = session
        self.config = config
        self.state = state

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = source_cfg["url"]
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]
        max_age_days = source_cfg.get("freshness_max_days") or self.config.get("freshness_max_days")

        headers: Dict[str, str] = {}
        state = self.state.get(source_cfg["id"], {})
        etag = state.get("etag")
        last_modified = state.get("last_modified")
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        jitter_sleep(jitter)
        resp = self.session.get(url, timeout=timeout, headers=headers)
        if resp.status_code == 304:
            return []
        resp.raise_for_status()
        raw = resp.text
        self.state.setdefault(source_cfg["id"], {})
        if resp.headers.get("ETag"):
            self.state[source_cfg["id"]]["etag"] = resp.headers.get("ETag")
        if resp.headers.get("Last-Modified"):
            self.state[source_cfg["id"]]["last_modified"] = resp.headers.get("Last-Modified")
        parsed = feedparser.parse(raw)
        items = []
        max_items = int(source_cfg.get("max_items", 10))
        for entry in parsed.entries[:max_items]:
            link = normalize_url(entry.get("link"))
            if not link:
                continue
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
            published_at_norm = normalize_datetime_from_entry(entry)
            if not is_fresh(published_at_norm, max_age_days):
                continue
            summary_text = html_to_text(entry.get("summary"))
            tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
            if not passes_keyword_filter(entry.get("title"), summary_text or content_value, tags, source_cfg, self.config):
                continue
            if not passes_content_quality(entry.get("title"), summary_text, content_value, source_cfg, self.config):
                continue
            item = {
                "source_id": source_cfg["id"],
                "item_id": entry.get("id") or entry.get("guid"),
                "url": link,
                "title": entry.get("title"),
                "published_at": published_at_norm,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_summary": summary_text or (content_value[:300] if content_value else None),
                "full_text": content_value or None,
                "tags": tags,
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
        ids_text, _ = fetch_url(self.session, ids_url, timeout=timeout, jitter=jitter)
        ids = json.loads(ids_text)

        max_items = int(source_cfg.get("max_items", 10))
        items = []
        for item_id in ids[:max_items]:
            item_url = f"{base}item/{item_id}.json"
            item_text, _ = fetch_url(self.session, item_url, timeout=timeout, jitter=jitter)
            data = json.loads(item_text)
            if not data:
                continue
            url = normalize_url(data.get("url") or f"https://news.ycombinator.com/item?id={item_id}")
            published_at = datetime.fromtimestamp(int(data.get("time", 0)), tz=timezone.utc).isoformat()
            max_age_days = source_cfg.get("freshness_max_days") or self.config.get("freshness_max_days")
            if not is_fresh(published_at, max_age_days):
                continue
            summary_text = html_to_text(data.get("text"))
            if not passes_keyword_filter(data.get("title"), summary_text, None, source_cfg, self.config):
                continue
            if not passes_content_quality(data.get("title"), summary_text, None, source_cfg, self.config):
                continue
            items.append(
                {
                    "source_id": source_cfg["id"],
                    "item_id": str(item_id),
                    "url": url,
                    "title": data.get("title"),
                    "published_at": published_at,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "raw_summary": summary_text,
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


class RedditAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any]):
        self.session = session
        self.config = config

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        base = source_cfg["url"].rstrip("/")
        endpoint = source_cfg.get("endpoint", "new")
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]

        max_items = int(source_cfg.get("max_items", 10))
        params = {"limit": max_items, "raw_json": 1}
        time_filter = source_cfg.get("time")
        if time_filter:
            params["t"] = time_filter
        query = urlencode(params, doseq=True)
        url = f"{base}/{endpoint}.json?{query}"

        text, _ = fetch_url(self.session, url, timeout=timeout, jitter=jitter)
        payload = json.loads(text)
        children = payload.get("data", {}).get("children", [])
        items: List[Dict[str, Any]] = []
        max_age_days = source_cfg.get("freshness_max_days") or self.config.get("freshness_max_days")
        for child in children:
            data = child.get("data") or {}
            title = data.get("title")
            post_url = normalize_url(data.get("url") or "")
            if not post_url:
                permalink = data.get("permalink")
                if permalink:
                    post_url = normalize_url(f"https://www.reddit.com{permalink}")
            created_utc = data.get("created_utc")
            published_at = None
            if created_utc:
                published_at = datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
            if not is_fresh(published_at, max_age_days):
                continue
            summary_text = html_to_text(data.get("selftext"))
            tags = [data.get("link_flair_text")] if data.get("link_flair_text") else None
            if not passes_keyword_filter(title, summary_text, tags, source_cfg, self.config):
                continue
            if not passes_content_quality(title, summary_text, None, source_cfg, self.config):
                continue
            items.append(
                {
                    "source_id": source_cfg["id"],
                    "item_id": str(data.get("id") or data.get("name")),
                    "url": post_url,
                    "title": title,
                    "published_at": published_at,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "raw_summary": summary_text,
                    "full_text": None,
                    "tags": tags,
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
        if not raw_html or len(raw_html.strip()) < 100:
            LOG.warning("Release notes fetch returned empty content for %s", source_cfg.get("id"))
            return []
        soup = BeautifulSoup(raw_html, "html.parser")
        container = soup.find("article") or soup.body or soup
        heading_tags = source_cfg.get("heading_tags", ["h2", "h3"])

        all_text = soup.get_text(" ", strip=True)
        page_updated = extract_updated_datetime(all_text)

        headings = container.find_all(heading_tags)
        max_items = int(source_cfg.get("max_items", 10))
        max_age_days = source_cfg.get("freshness_max_days") or self.config.get("freshness_max_days")
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
            if not is_fresh(published_at, max_age_days):
                continue
            item_url = normalize_url(f"{url}#{slugify(title)}")
            if not passes_content_quality(title, section_text, section_text, source_cfg, self.config):
                continue
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


class ListingPageAdapter:
    def __init__(self, session: requests.Session, config: Dict[str, Any]):
        self.session = session
        self.config = config

    def fetch_items(self, source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = source_cfg["url"]
        timeout = int(self.config["http"]["timeout_seconds"])
        jitter = self.config["http"]["jitter_seconds"]
        max_items = int(source_cfg.get("max_items", 10))
        max_age_days = source_cfg.get("freshness_max_days") or self.config.get("freshness_max_days")
        link_regex = source_cfg.get("item_link_regex")
        if not link_regex:
            raise ValueError(f"item_link_regex missing for source {source_cfg.get('id')}")
        pattern = re.compile(link_regex)
        title_separator = str(source_cfg.get("listing_title_separator", "|"))
        title_index = int(source_cfg.get("listing_title_index", 0))

        raw_html = fetch_url_with_jina_fallback(
            self.session, self.config, source_cfg, url, timeout=timeout, jitter=jitter
        )
        soup = BeautifulSoup(raw_html, "html.parser")

        candidates: List[Tuple[str, str, Optional[str]]] = []
        seen_links: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            absolute_url = normalize_url(urljoin(url, href))
            if not absolute_url or absolute_url in seen_links:
                continue
            if not pattern.search(href) and not pattern.search(absolute_url):
                continue
            if absolute_url.rstrip("/") == url.rstrip("/"):
                continue

            anchor_text = normalize_text(anchor.get_text(" | ", strip=True)) or ""
            title = extract_listing_title(anchor_text, separator=title_separator, index=title_index)
            published_at = extract_date_from_text(anchor_text)
            candidates.append((absolute_url, title, published_at))
            seen_links.add(absolute_url)
            if len(candidates) >= max_items * 3:
                break

        items: List[Dict[str, Any]] = []
        for article_url, fallback_title, listing_published_at in candidates:
            article_html = fetch_url_with_jina_fallback(
                self.session, self.config, source_cfg, article_url, timeout=timeout, jitter=jitter
            )
            article_soup = BeautifulSoup(article_html, "html.parser")
            title = extract_article_title(article_soup, fallback_title)
            body = extract_article_text(article_soup)
            published_at = extract_article_datetime(article_soup, listing_published_at)

            if not is_fresh(published_at, max_age_days):
                continue
            summary = body[:300] if body else None
            if not passes_keyword_filter(title, summary, None, source_cfg, self.config):
                continue
            if not passes_content_quality(title, summary, body, source_cfg, self.config):
                continue

            items.append(
                {
                    "source_id": source_cfg["id"],
                    "item_id": slugify(title or article_url),
                    "url": article_url,
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
            )
            if len(items) >= max_items:
                break

        return items


def build_adapters(session: requests.Session, config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rss": RSSAdapter(session, config, state),
        "hackernews": HackerNewsAdapter(session, config),
        "reddit": RedditAdapter(session, config),
        "release_notes": ReleaseNotesAdapter(session, config),
        "listing_page": ListingPageAdapter(session, config),
    }


def run_scraper(config_path: str, smoke_test: bool = False) -> int:
    config = load_config(config_path)
    storage = SQLiteStorage(config["db_path"])
    source_state = load_source_state()
    all_items: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    semantic_enabled = bool(config.get("semantic_dedupe_enabled", True))
    semantic_hours = int(config.get("semantic_dedupe_hours", 24))
    semantic_threshold = float(config.get("semantic_dedupe_threshold", 0.86))
    semantic_max_compare = int(config.get("semantic_dedupe_max_compare", 200))
    recent_titles = storage.fetch_recent_titles(semantic_hours) if semantic_enabled else []
    recent_tokens: List[List[str]] = [
        tokens for title in recent_titles if (tokens := tokenize_title(title))
    ]

    sources = config.get("sources", [])
    if smoke_test:
        preferred_ids = {"techcrunch_feed", "wired_ai", "mit_news_ai", "nvidia_blog"}
        preferred = [s for s in sources if s.get("id") in preferred_ids]
        sources = (preferred or sources)[:2]
    else:
        sources = sorted(sources, key=lambda src: int(src.get("tier", 2)))

    def fetch_source_worker(source_cfg: Dict[str, Any], state_entry: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], int, Dict[str, Any]]:
        session = build_session(config)
        local_state = {source_cfg["id"]: dict(state_entry)}
        adapters = build_adapters(session, config, local_state)
        src_type = source_cfg.get("type")
        adapter = adapters.get(src_type)
        if not adapter:
            raise ValueError(f"No adapter for source type: {src_type}")
        start_ts = time.time()
        items = adapter.fetch_items(source_cfg)
        elapsed_ms = int((time.time() - start_ts) * 1000)
        updated_state = local_state.get(source_cfg["id"], {})
        return source_cfg["id"], items, elapsed_ms, updated_state

    work_sources: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for source_cfg in sources:
        source_id = source_cfg.get("id", "unknown")
        if source_cfg.get("enabled", True) is False:
            LOG.info("Skipping %s (disabled)", source_id)
            continue
        state_entry = source_state.get(source_id, {})
        if is_disabled(state_entry):
            LOG.warning("Skipping %s due to hard disable until %s", source_id, state_entry.get("disabled_until"))
            continue
        cooldown_minutes = int(source_cfg.get("cooldown_minutes", config.get("source_cooldown_minutes", 30)))
        max_failures = int(source_cfg.get("max_failures", config.get("source_max_failures", 3)))
        last_fail_ts = state_entry.get("last_fail_ts")
        fail_count = int(state_entry.get("fail_count", 0))
        if last_fail_ts and fail_count >= max_failures:
            try:
                last_fail_dt = datetime.fromisoformat(last_fail_ts)
                if datetime.now(timezone.utc) < last_fail_dt + timedelta(minutes=cooldown_minutes):
                    LOG.warning("Skipping %s due to cooldown (fail_count=%s)", source_id, fail_count)
                    continue
            except ValueError:
                pass
        LOG.info("Fetching source: %s", source_cfg.get("name"))
        work_sources.append((source_cfg, state_entry))

    max_workers = int(config.get("http", {}).get("max_workers", 6))
    enrich_session = build_session(config)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for source_cfg, state_entry in work_sources:
            future = executor.submit(fetch_source_worker, source_cfg, state_entry)
            future_map[future] = (source_cfg, state_entry)

        for future in as_completed(future_map):
            source_cfg, state_entry = future_map[future]
            source_id = source_cfg.get("id", "unknown")
            fail_count = int(state_entry.get("fail_count", 0))
            try:
                source_id, items, elapsed_ms, updated_state = future.result()
            except requests.RequestException as exc:
                status_code = getattr(exc.response, "status_code", None)
                LOG.warning("Fetch failed for %s: %s", source_cfg.get("id"), exc)
                source_state.setdefault(source_id, {})
                source_state[source_id]["fail_count"] = fail_count + 1
                source_state[source_id]["last_fail_ts"] = datetime.now(timezone.utc).isoformat()
                source_state[source_id]["last_error"] = str(exc)
                hard_codes = set(config.get("hard_fail_status_codes", [401, 403, 451]))
                hard_cooldown_hours = int(config.get("hard_fail_cooldown_hours", 24))
                if status_code in hard_codes:
                    source_state[source_id]["hard_fail_count"] = int(state_entry.get("hard_fail_count", 0)) + 1
                    disabled_until = datetime.now(timezone.utc) + timedelta(hours=hard_cooldown_hours)
                    source_state[source_id]["disabled_until"] = disabled_until.isoformat()
                    LOG.warning(
                        "Hard disabled %s for %s hours due to status %s",
                        source_id,
                        hard_cooldown_hours,
                        status_code,
                    )
                continue
            except Exception as exc:
                LOG.warning("Fetch failed for %s: %s", source_cfg.get("id"), exc)
                source_state.setdefault(source_id, {})
                source_state[source_id]["fail_count"] = fail_count + 1
                source_state[source_id]["last_fail_ts"] = datetime.now(timezone.utc).isoformat()
                source_state[source_id]["last_error"] = str(exc)
                continue

            filtered_items: List[Dict[str, Any]] = []
            for item in items:
                if should_enrich(item.get("url"), config, source_cfg):
                    enriched = fetch_full_text(enrich_session, config, item["url"])
                    if enriched:
                        item["full_text"] = enriched
                    elif item.get("raw_summary") and not item.get("full_text"):
                        item["full_text"] = item["raw_summary"]
                normalize_item_fields(item)
                if item.get("raw_summary") and not item.get("full_text"):
                    item["full_text"] = item["raw_summary"]
                dedupe_key = make_dedupe_key(item.get("url"), item.get("title"))
                if dedupe_key and dedupe_key in seen_keys:
                    LOG.debug("Skipping duplicate item: %s (%s)", item.get("title"), item.get("url"))
                    continue
                if dedupe_key:
                    seen_keys.add(dedupe_key)
                if semantic_enabled and item.get("title"):
                    tokens = tokenize_title(item.get("title"))
                    if is_semantic_duplicate(tokens, recent_tokens, semantic_threshold, semantic_max_compare):
                        LOG.info("Skipping semantic duplicate item: %s", item.get("title"))
                        continue
                    if tokens:
                        recent_tokens.append(tokens)
                filtered_items.append(item)
            all_items.extend(filtered_items)
            source_state.setdefault(source_id, {})
            source_state[source_id].update(updated_state or {})
            source_state[source_id]["last_success_ts"] = datetime.now(timezone.utc).isoformat()
            source_state[source_id]["last_latency_ms"] = elapsed_ms
            source_state[source_id]["last_items"] = len(filtered_items)
            source_state[source_id]["fail_count"] = 0

    saved = storage.upsert_items(all_items)
    save_source_state(source_state)
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
