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
    MAX_COMPRESSED_CHARS,
    MAX_ITEMS_PER_RUN,
    LOCAL_MODEL_N_CTX,
    LOCAL_MODEL_PARAMS_B,
    LOCAL_MODEL_QUANT,
    LLM_THROTTLE_SECONDS,
    MIN_RATIONALE_CHARS,
    MIN_ACTION_ITEMS,
    MAX_ACTION_ITEMS,
    ALLOWED_ROLES,
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


def _clean_boilerplate(text: str) -> str:
    patterns = [
        r"subscribe",
        r"newsletter",
        r"sign up",
        r"follow us",
        r"privacy policy",
        r"terms of service",
        r"all rights reserved",
        r"cookie",
        r"advertis",
        r"share this",
        r"read more",
        r"related articles",
        r"источник",
        r"подпис",
        r"рассылка",
        r"правила",
        r"политика конфиденциальности",
        r"условия использования"
    ]
    cleaned_lines = []
    for line in text.splitlines():
        lower = line.strip().lower()
        if not lower:
            continue
        if any(re.search(pat, lower) for pat in patterns):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences


def _score_sentence(sentence: str) -> int:
    keywords = [
        "announce",
        "announced",
        "release",
        "released",
        "launch",
        "launched",
        "update",
        "updated",
        "new",
        "model",
        "api",
        "pricing",
        "availability",
        "benchmark",
        "paper",
        "research",
        "security",
        "policy",
        "risk",
        "funding",
        "partnership",
        "agreement",
        "acquisition",
        "report",
        "open-source",
        "open source",
        "dataset",
        "agent",
        "reasoning",
        "inference",
        "token",
        "latency",
        "deployment",
        "регуля",
        "безопасн",
        "обнов",
        "релиз",
        "запуск",
        "модель",
        "данные",
        "исслед",
        "контракт",
        "партнер",
        "цена",
        "стоимость",
        "план",
    ]
    score = 0
    lower = sentence.lower()
    if any(char.isdigit() for char in sentence):
        score += 2
    for key in keywords:
        if key in lower:
            score += 1
    score += max(0, 40 - abs(len(sentence) - 180) // 4)
    return score


def compress_full_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    cleaned = _clean_boilerplate(text)
    if len(cleaned) <= max_chars:
        return cleaned

    sentences = _split_sentences(cleaned)
    if not sentences:
        return trim_text(cleaned, max_chars)

    head = sentences[:2]
    tail = sentences[-1:] if len(sentences) > 3 else []
    middle = sentences[2:-1] if len(sentences) > 3 else sentences[2:]
    ranked = sorted(middle, key=_score_sentence, reverse=True)
    picked = head + ranked[:12] + tail

    seen = set()
    unique = []
    for sentence in picked:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)

    compressed = " ".join(unique).strip()
    if len(compressed) > max_chars:
        return trim_text(compressed, max_chars)
    return compressed


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


def extract_json(payload: Optional[str]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")
    if not isinstance(payload, str) or not payload.strip():
        return None
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


def limit_sentences(text: str, max_sentences: int = 2) -> str:
    if not text:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:max_sentences]).strip()


def validate_payload(payload: Dict[str, Any], logger: logging.Logger, url: str) -> bool:
    if payload.get("impact_score") is None:
        logger.warning("Missing impact_score for %s", url)
        return False
    target_role = payload.get("target_role", "other")
    if target_role not in ALLOWED_ROLES:
        payload["target_role"] = "other"
    rationale = payload.get("impact_rationale", "")
    if not rationale or len(rationale) < MIN_RATIONALE_CHARS:
        logger.warning("Rationale too short for %s", url)
        return False
    action_items = payload.get("action_items", [])
    if len(action_items) < MIN_ACTION_ITEMS:
        logger.warning("Action items too few for %s", url)
        return False
    if len(action_items) > MAX_ACTION_ITEMS:
        payload["action_items"] = action_items[:MAX_ACTION_ITEMS]
    return True


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
    compressed = compress_full_text(full_text, MAX_COMPRESSED_CHARS)
    return (
        "NEWS_ITEM\n"
        f"SOURCE_ID: {source_id}\n"
        f"TITLE: {title}\n"
        f"URL: {url}\n"
        f"PUBLISHED_AT: {published_at}\n"
        f"SUMMARY: {raw_summary}\n\n"
        f"FULL_TEXT:\n{compressed}\n"
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
            before_len = len(full_text)
            user_prompt = build_user_prompt(
                source_id=source_id,
                url=url,
                title=title or "",
                published_at=published_at or "",
                raw_summary=raw_summary or "",
                full_text=trim_text(full_text, MAX_INPUT_CHARS),
            )
            after_len = len(user_prompt)
            logger.debug("context_compress url=%s raw_len=%s prompt_len=%s", url, before_len, after_len)
            try:
                response = client.generate(prompt, user_prompt)
            except Exception as exc:
                logger.warning("LLM generation failed for %s: %s", url, exc)
                if LLM_THROTTLE_SECONDS > 0:
                    time.sleep(LLM_THROTTLE_SECONDS)
                continue

            if not response:
                logger.warning("Empty LLM response for %s", url)
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
                "impact_rationale": limit_sentences(sanitize_text(rationale_raw, 360), 2),
                "action_items": action_items,
                "tags": tags,
                "entities": entities,
                "confidence": normalize_confidence(parsed.get("confidence")),
            }

            if not validate_payload(payload, logger, url):
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
