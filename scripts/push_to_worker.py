import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

import requests
import yaml

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


def get_state_path() -> Path:
    base = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / "SearchAInews" / "state"
    base.mkdir(parents=True, exist_ok=True)
    return base / "sync_state.json"


def load_config(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8") as f:
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
    path.write_text(json.dumps({"last_id": last_id}, ensure_ascii=True), encoding="utf-8")


def fetch_items(db_path: str, last_id: int, limit: int) -> List[Dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, title, url, raw_summary, full_text, impact_score, impact_rationale,
                   action_items_json, target_role, tags_json, published_at
            FROM items
            WHERE impact_score IS NOT NULL
              AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (last_id, limit),
        )
        rows = cursor.fetchall()
    items = []
    for row in rows:
        (
            item_id,
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
        ) = row
        items.append(
            {
                "id": item_id,
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
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Push scored items to Cloudflare Worker.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger = setup_logging()
    _load_dotenv(ROOT / ".env")

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

    state = load_state()
    last_id = int(state.get("last_id", 0))
    items = fetch_items(db_path, last_id, args.limit)
    if not items:
        logger.info("No new scored items to push.")
        return 0

    payload = {"items": items}
    if args.dry_run:
        logger.info("Dry run: would send %s items to %s", len(items), ingest_url)
        return 0

    response = requests.post(
        ingest_url,
        headers={"X-Ingest-Token": ingest_secret, "Content-Type": "application/json"},
        data=json.dumps(payload, ensure_ascii=True),
        timeout=30,
    )
    if response.status_code != 200:
        logger.error("Ingest failed: %s %s", response.status_code, response.text)
        return 1

    max_id = max(item["id"] for item in items if isinstance(item.get("id"), int))
    save_state(max_id)
    logger.info("Pushed %s items. last_id=%s", len(items), max_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
