import argparse
import json
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_state_dir() -> Path:
    env_dir = os.environ.get("LOCALAPPDATA")
    if env_dir:
        base = Path(env_dir)
    else:
        expanded = os.path.expandvars(r"%LOCALAPPDATA%")
        base = Path(tempfile.gettempdir()) if expanded == "%LOCALAPPDATA%" else Path(expanded)
    state_dir = base / "SearchAInews" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_state_path() -> Path:
    return get_state_dir() / "sync_state.json"


def load_config(path: Path) -> Dict[str, str]:
    resolved = path if path.is_absolute() else ROOT / path
    with resolved.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("push_to_worker")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def load_state() -> Dict[str, int]:
    path = get_state_path()
    if not path.exists():
        return {"last_id": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_id": 0}


def save_state(last_id: int) -> None:
    path = get_state_path()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps({"last_id": last_id}, ensure_ascii=True), encoding="utf-8")
    temp_path.replace(path)


def mark_items_pushed(db_path: str, ids: List[int]) -> None:
    if not ids:
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout = 5000;")
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"UPDATE items SET pushed_to_worker = 1 WHERE id IN ({placeholders})", ids)


def fetch_items(db_path: str, last_id: int = 0, limit: int = 200) -> List[Dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout = 5000;")
        cursor = conn.execute("PRAGMA table_info(items);")
        cols = {row[1] for row in cursor.fetchall()}
        if "pushed_to_worker" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN pushed_to_worker INTEGER DEFAULT 0;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_pushed ON items(pushed_to_worker, impact_score);")

        cursor = conn.execute(
            """
            SELECT id, source_id, title, url, raw_summary, full_text, impact_score, impact_rationale,
                   action_items_json, target_role, tags_json, published_at, discussion_context, content_profile
            FROM items
            WHERE impact_score IS NOT NULL
              AND (pushed_to_worker = 0 OR pushed_to_worker IS NULL)
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
    items = []
    for row in rows:
        (
            item_id,
            source_id,
            title,
            url,
            raw_summary,
            full_text,
            impact_score,
            impact_rationale,
            action_items_json,
            target_role,
            tags_json,
            published_at,
            discussion_context,
            content_profile,
        ) = row
        items.append(
            {
                "id": item_id,
                "source_id": source_id,
                "title": title,
                "url": url,
                "raw_summary": raw_summary,
                "full_text": full_text,
                "impact_score": impact_score,
                "impact_rationale": impact_rationale,
                "action_items_json": action_items_json,
                "target_role": target_role,
                "tags_json": tags_json,
                "published_at": published_at,
                "discussion_context": discussion_context,
                "content_profile": content_profile,
            }
        )
    return items


def get_db_stats(db_path: str) -> Dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT
              COALESCE(MAX(id), 0) AS max_id,
              COALESCE(MAX(CASE WHEN impact_score IS NOT NULL THEN id END), 0) AS max_scored_id,
              COALESCE(COUNT(CASE WHEN impact_score IS NOT NULL THEN 1 END), 0) AS scored_count
            FROM items
            """
        )
        row = cursor.fetchone() or (0, 0, 0)
    return {
        "max_id": int(row[0] or 0),
        "max_scored_id": int(row[1] or 0),
        "scored_count": int(row[2] or 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Push scored items to Cloudflare Worker.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger = setup_logging()
    _load_dotenv(ROOT / ".env")
    persist_state = not args.dry_run

    ingest_url = os.getenv("INGEST_URL", "").strip()
    ingest_secret = os.getenv("INGEST_SECRET", "").strip()
    if not ingest_url or not ingest_secret:
        logger.warning("INGEST_URL or INGEST_SECRET not set; skipping.")
        return 1

    config = load_config(Path(args.config))
    db_path = os.path.expandvars(config.get("db_path", ""))
    if not db_path:
        logger.error("db_path missing in config.yaml")
        return 1

    stats = get_db_stats(db_path)
    state = load_state()
    last_id = int(state.get("last_id", 0))
    if stats["max_id"] > 0 and last_id > stats["max_id"]:
        logger.warning(
            "Sync state is ahead of DB max id (last_id=%s, max_id=%s). Resetting state to 0.",
            last_id,
            stats["max_id"],
        )
        last_id = 0
        if persist_state:
            save_state(last_id)

    items = fetch_items(db_path, last_id, args.limit)
    if not items:
        if stats["scored_count"] > 0 and stats["max_scored_id"] < last_id:
            logger.warning(
                "Sync state is ahead of current scored frontier (last_id=%s, max_scored_id=%s). "
                "Resetting state to 0 and replaying scored items.",
                last_id,
                stats["max_scored_id"],
            )
            last_id = 0
            if persist_state:
                save_state(last_id)
            items = fetch_items(db_path, last_id, args.limit)
        if not items:
            logger.info("No new scored items to push.")
            return 0

    payload = {"items": items}
    if args.dry_run:
        logger.info("Dry run: would send %s items to %s", len(items), ingest_url)
        return 0

    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    session.mount("http://", HTTPAdapter(max_retries=retry_strategy))

    response = session.post(
        ingest_url,
        headers={"X-Ingest-Token": ingest_secret, "Content-Type": "application/json"},
        data=json.dumps(payload, ensure_ascii=True),
        timeout=30,
    )
    if response.status_code != 200:
        logger.error("Ingest failed: %s %s", response.status_code, response.text)
        return 1

    item_ids = [item["id"] for item in items if isinstance(item.get("id"), int)]
    mark_items_pushed(db_path, item_ids)
    max_id = max(item_ids) if item_ids else last_id
    if persist_state:
        save_state(max_id)
    logger.info("Pushed %s items. last_id=%s", len(items), max_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
