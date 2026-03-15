import argparse
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ai_config import (
    DEFAULT_DB_CONFIG_PATH,
    MAX_INPUT_CHARS,
    MAX_ITEMS_PER_RUN,
    LOCAL_MODEL_N_CTX,
    LOCAL_MODEL_PARAMS_B,
    LOCAL_MODEL_QUANT,
    LLM_THROTTLE_SECONDS,
    calculate_vram_budget,
    get_log_path,
    get_prompt_path,
)
from llm_client import HybridLLMClient


def setup_logging() -> logging.Logger:
    log_path = get_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_analyzer")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]"


def fetch_pending(
    conn: sqlite3.Connection, limit: int
) -> List[Tuple[Any, ...]]:
    cursor = conn.execute(
        """
        SELECT id, source_id, url, title, published_at, raw_summary, full_text
        FROM items
        WHERE impact_score IS NULL
          AND full_text IS NOT NULL
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def extract_json(payload: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(payload[start : end + 1])
        except json.JSONDecodeError:
            return None


def normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if not value.strip():
            return []
        return [value.strip()]
    return [str(value).strip()]


def strip_code_blocks(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def sanitize_text(text: str, max_len: int) -> str:
    cleaned = strip_code_blocks(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return cleaned


def normalize_score(value: Any) -> Optional[int]:
    try:
        score = float(value)
        score = int(round(score))
        if score < 1:
            return 1
        if score > 5:
            return 5
        return score
    except (TypeError, ValueError):
        return None


def normalize_confidence(value: Any) -> Optional[float]:
    try:
        conf = float(value)
        if conf < 0:
            return 0.0
        if conf > 1:
            return 1.0
        return conf
    except (TypeError, ValueError):
        return None


def update_item(
    conn: sqlite3.Connection,
    item_id: int,
    payload: Dict[str, Any],
) -> None:
    conn.execute(
        """
        UPDATE items
        SET impact_score = ?,
            target_role = ?,
            impact_rationale = ?,
            action_items_json = ?,
            tags_json = ?,
            entities_json = ?,
            confidence = ?
        WHERE id = ?
        """,
        (
            payload.get("impact_score"),
            payload.get("target_role"),
            payload.get("impact_rationale"),
            json.dumps(payload.get("action_items"), ensure_ascii=False),
            json.dumps(payload.get("tags"), ensure_ascii=False),
            json.dumps(payload.get("entities"), ensure_ascii=False),
            payload.get("confidence"),
            item_id,
        ),
    )


def build_user_prompt(
    source_id: str,
    url: str,
    title: str,
    published_at: str,
    raw_summary: str,
    full_text: str,
) -> str:
    return (
        "NEWS_ITEM\n"
        f"SOURCE_ID: {source_id}\n"
        f"TITLE: {title}\n"
        f"URL: {url}\n"
        f"PUBLISHED_AT: {published_at}\n"
        f"SUMMARY: {raw_summary}\n\n"
        f"FULL_TEXT:\n{full_text}\n"
    )


def analyze(
    db_path: str,
    prompt_path: Path,
    limit: int,
    logger: logging.Logger,
) -> int:
    prompt = read_prompt(prompt_path)
    client = HybridLLMClient(logger)

    budget = calculate_vram_budget(LOCAL_MODEL_PARAMS_B, LOCAL_MODEL_QUANT, LOCAL_MODEL_N_CTX)
    logger.info("vram_budget=%s", budget)

    updated = 0
    with sqlite3.connect(db_path) as conn:
        rows = fetch_pending(conn, limit)
        if not rows:
            logger.warning("No pending items found.")
            return 0

        for row in rows:
            item_id, source_id, url, title, published_at, raw_summary, full_text = row
            if not full_text:
                continue
            user_prompt = build_user_prompt(
                source_id=source_id,
                url=url,
                title=title or "",
                published_at=published_at or "",
                raw_summary=raw_summary or "",
                full_text=trim_text(full_text, MAX_INPUT_CHARS),
            )
            try:
                response = client.generate(prompt, user_prompt)
            except Exception as exc:
                logger.warning("LLM generation failed for %s: %s", url, exc)
                if LLM_THROTTLE_SECONDS > 0:
                    time.sleep(LLM_THROTTLE_SECONDS)
                continue

            parsed = extract_json(response)
            if not parsed:
                logger.warning("Invalid JSON for %s", url)
                continue

            rationale_raw = str(parsed.get("impact_rationale") or "").strip()
            action_items = normalize_list(parsed.get("action_items"))
            action_items = [
                sanitize_text(item, 140) for item in action_items if sanitize_text(item, 140)
            ][:4]
            tags = normalize_list(parsed.get("tags"))
            tags = [sanitize_text(tag, 40) for tag in tags if sanitize_text(tag, 40)][:8]
            entities = normalize_list(parsed.get("entities"))
            entities = [sanitize_text(ent, 60) for ent in entities if sanitize_text(ent, 60)][:8]

            payload = {
                "impact_score": normalize_score(parsed.get("impact_score")),
                "target_role": str(parsed.get("target_role") or "other").strip() or "other",
                "impact_rationale": sanitize_text(rationale_raw, 360),
                "action_items": action_items,
                "tags": tags,
                "entities": entities,
                "confidence": normalize_confidence(parsed.get("confidence")),
            }

            if payload["impact_score"] is None:
                logger.warning("Missing impact_score for %s", url)
                continue

            update_item(conn, item_id, payload)
            updated += 1
            if LLM_THROTTLE_SECONDS > 0:
                time.sleep(LLM_THROTTLE_SECONDS)

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze news items with LLM.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_DB_CONFIG_PATH),
        help="Path to config.yaml",
    )
    parser.add_argument("--limit", type=int, default=MAX_ITEMS_PER_RUN)
    args = parser.parse_args()

    logger = setup_logging()
    config = load_config(Path(args.config))
    db_path = config.get("db_path")
    if not db_path:
        logger.warning("db_path missing in config.")
        return
    db_path = os.path.expandvars(db_path)

    prompt_path = get_prompt_path()
    if not prompt_path.exists():
        logger.warning("Prompt file missing: %s", prompt_path)
        return

    updated = analyze(db_path, prompt_path, args.limit, logger)
    logger.warning("Updated items: %s", updated)


if __name__ == "__main__":
    main()
