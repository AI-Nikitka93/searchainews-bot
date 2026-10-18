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
    MAX_DISCUSSION_CHARS,
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


PRIORITY_SOURCE_IDS = {
    "openai_news",
    "openai_blog",
    "openai_model_release_notes",
    "openai_chatgpt_release_notes",
    "anthropic_release_notes",
    "anthropic_api_release_notes",
    "mistral_ai_news",
    "google_blog_ai",
    "google_blog_ai_tech",
    "deepmind_blog",
    "huggingface_blog",
    "nvidia_blog",
    "nvidia_dev_blog",
    "together_ai_blog",
    "ollama_blog",
    "vllm_blog",
    "langchain_blog",
    "ai2_research",
    "import_ai",
    "interconnects_ai",
    "ahead_of_ai",
}

ANALYZER_COMMIT_INTERVAL = max(1, int(os.getenv("ANALYZER_COMMIT_INTERVAL", "5")))

PRIORITY_KEYWORDS = [
    "introducing",
    "new model",
    "model release",
    "released model",
    "launches model",
    "launching model",
    "gpt-",
    "claude",
    "gemini",
    "llama",
    "qwen",
    "mistral",
    "deepseek",
    "pixtral",
    "magistral",
    "devstral",
    "reasoning model",
    "foundation model",
    "open model",
    "weights released",
    "chatgpt release notes",
    "model release notes",
    "релиз модели",
    "новая модель",
    "выпустила модель",
    "представила модель",
]


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
    conn: sqlite3.Connection, limit: int, source_ids: Optional[List[str]] = None
) -> List[Tuple[Any, ...]]:
    query = """
        SELECT id, source_id, url, title, published_at, raw_summary, full_text, discussion_context
        FROM items
        WHERE impact_score IS NULL
          AND full_text IS NOT NULL
    """
    params: List[Any] = []
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        query += f" AND source_id IN ({placeholders})"
        params.extend(source_ids)
    query += " ORDER BY published_at DESC LIMIT ?"
    params.append(limit)
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def fetch_pending_priority(
    conn: sqlite3.Connection, limit: int, source_ids: Optional[List[str]] = None
) -> List[Tuple[Any, ...]]:
    if limit <= 0:
        return []

    params: List[Any] = []
    priority_filters: List[str] = []
    base_filters: List[str] = [
        "impact_score IS NULL",
        "full_text IS NOT NULL",
    ]

    if source_ids:
        source_placeholders = ",".join("?" for _ in source_ids)
        base_filters.append(f"source_id IN ({source_placeholders})")
        params.extend(source_ids)

    if PRIORITY_SOURCE_IDS:
        source_placeholders = ",".join("?" for _ in PRIORITY_SOURCE_IDS)
        priority_filters.append(f"source_id IN ({source_placeholders})")
        params.extend(sorted(PRIORITY_SOURCE_IDS))

    keyword_clauses: List[str] = []
    for keyword in PRIORITY_KEYWORDS:
        pattern = f"%{keyword.lower()}%"
        keyword_clauses.append("LOWER(COALESCE(title, '')) LIKE ?")
        params.append(pattern)
        keyword_clauses.append("LOWER(COALESCE(raw_summary, '')) LIKE ?")
        params.append(pattern)
        keyword_clauses.append("LOWER(COALESCE(url, '')) LIKE ?")
        params.append(pattern)
    if keyword_clauses:
        priority_filters.append("(" + " OR ".join(keyword_clauses) + ")")

    if not priority_filters:
        return fetch_pending(conn, limit, source_ids)

    priority_query = f"""
        SELECT id, source_id, url, title, published_at, raw_summary, full_text, discussion_context
        FROM items
        WHERE {' AND '.join(base_filters)}
          AND ({' OR '.join(priority_filters)})
        ORDER BY published_at DESC
        LIMIT ?
    """
    priority_rows = conn.execute(priority_query, (*params, limit)).fetchall()
    if len(priority_rows) >= limit:
        return priority_rows

    selected_ids = [row[0] for row in priority_rows]
    remaining = limit - len(priority_rows)
    extra_query = (
        "SELECT id, source_id, url, title, published_at, raw_summary, full_text, discussion_context "
        "FROM items WHERE " + " AND ".join(base_filters)
    )
    extra_params: List[Any] = []
    if source_ids:
        extra_params.extend(source_ids)
    if selected_ids:
        placeholders = ",".join("?" for _ in selected_ids)
        extra_query += f" AND id NOT IN ({placeholders})"
        extra_params.extend(selected_ids)
    extra_query += " ORDER BY published_at DESC LIMIT ?"
    extra_params.append(remaining)
    extra_rows = conn.execute(extra_query, extra_params).fetchall()
    return priority_rows + extra_rows


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


def strip_citation_brackets(text: str) -> str:
    if not text:
        return ""
    # Strip web/search citations like 【1†source】 or 【12】
    cleaned = re.sub(r"【[^】]*】", "", text)
    # Strip markdown footnotes like [^1] or [^note]
    cleaned = re.sub(r"\[\^[\w-]+\]", "", cleaned)
    # Strip bracket numbers or ranges like [1], [1, 2], [1-3], [1][2][3]
    cleaned = re.sub(r"(?:\[\s*\d+(?:\s*[,;–—\-]\s*\d+)*\s*\])+", "", cleaned)
    # Strip [citation needed], [источник...]
    cleaned = re.sub(r"\[(?:citation\s+needed|источник(?:\s+не\s+указан)?)\]", "", cleaned, flags=re.IGNORECASE)
    # Clean up spaces before punctuation caused by citation removal
    cleaned = re.sub(r"\s+([.,!?;:])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_text(text: str, max_len: int, append_ellipsis: bool = False) -> str:
    cleaned = strip_code_blocks(text)
    cleaned = strip_citation_brackets(cleaned)
    if len(cleaned) <= max_len:
        return cleaned

    target_len = max(1, max_len - 1) if append_ellipsis else max_len
    head = cleaned[:target_len + 1]
    last_space = head.rfind(" ")
    cutoff = last_space if last_space > 0 else target_len
    result = re.sub(r"[,;:\-–—\s]+$", "", head[:cutoff]).strip()
    if append_ellipsis:
        result += "…"
    return result


def clean_action_item(item: str, max_len: int = 140) -> Optional[str]:
    if not item:
        return None
    cleaned = strip_code_blocks(item)
    cleaned = strip_citation_brackets(cleaned)
    if not cleaned:
        return None
    meta_pattern = r"(?i)(проверить\s+(?:cited[- ]?источник|источник[иов]|ссылк[иу])|check\s+(?:cited[- ]?source|sources|citations?))"
    if re.search(meta_pattern, cleaned):
        return None
    if len(cleaned) <= max_len:
        return cleaned
    head = cleaned[:max_len]
    last_space = head.rfind(" ")
    cutoff = last_space if last_space > 0 else max_len
    return re.sub(r"[,;:\-–—\s]+$", "", head[:cutoff]).strip()


def format_impact_rationale(text: str, max_chars: int = 320, max_sentences: int = 3) -> str:
    if not text:
        return ""
    cleaned = strip_code_blocks(text)
    cleaned = strip_citation_brackets(cleaned)
    if not cleaned:
        return ""

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", cleaned) if s.strip()]

    valid_sentences: List[str] = []
    current_len = 0
    for s in raw_sentences:
        if not re.search(r'[.!?…]["»\']?$', s):
            continue
        new_len = current_len + (1 if valid_sentences else 0) + len(s)
        if new_len > max_chars:
            break
        valid_sentences.append(s)
        current_len = new_len
        if len(valid_sentences) >= max_sentences:
            break

    if valid_sentences:
        return " ".join(valid_sentences)

    # Fallback: slice safely at word boundary, never mid-word
    head = cleaned[:max_chars]
    last_space = head.rfind(" ")
    cutoff = last_space if last_space > 0 else max_chars
    return re.sub(r"[,;:\-–—\s]+$", "", head[:cutoff]).strip() + "."


def limit_sentences(text: str, max_sentences: int = 3) -> str:
    if not text:
        return text
    cleaned = strip_citation_brackets(text)
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", cleaned) if p.strip()]
    valid_sentences = [p for p in parts if re.search(r'[.!?…]["»\']?$', p)]
    if valid_sentences:
        return " ".join(valid_sentences[:max_sentences])
    if parts:
        head = parts[0]
        return re.sub(r"[,;:\-–—\s]+$", "", head) + "."
    return cleaned


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
    if not re.search(r'[.!?…]["»\']?$', rationale.strip()):
        logger.warning("Rationale does not end with terminal punctuation for %s: %r", url, rationale)
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
    content_profile: Optional[str] = None,
) -> None:
    profile_val = content_profile or payload.get("content_profile")
    conn.execute(
        """
        UPDATE items
        SET impact_score = ?,
            target_role = ?,
            impact_rationale = ?,
            action_items_json = ?,
            tags_json = ?,
            entities_json = ?,
            confidence = ?,
            content_profile = COALESCE(?, content_profile)
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
            profile_val,
            item_id,
        ),
    )


def sanitize_discussion(text: Optional[str], max_chars: int = MAX_DISCUSSION_CHARS) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = cleaned.replace("`", "'")
    cleaned = re.sub(r"(?i)(system\s*prompt|ignore\s*previous\s*instructions|you\s*are\s*now)", "[REDACTED]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "..."
    return cleaned


def build_user_prompt(
    source_id: str,
    url: str,
    title: str,
    published_at: str,
    raw_summary: str,
    full_text: str,
    discussion_context: Optional[str] = None,
) -> str:
    clean_discussion = sanitize_discussion(discussion_context, MAX_DISCUSSION_CHARS)
    if clean_discussion:
        remaining_chars = max(1500, MAX_COMPRESSED_CHARS - len(clean_discussion) - 100)
    else:
        remaining_chars = MAX_COMPRESSED_CHARS
    compressed = compress_full_text(full_text, remaining_chars)
    prompt = (
        "NEWS_ITEM\n"
        f"SOURCE_ID: {source_id}\n"
        f"TITLE: {title}\n"
        f"URL: {url}\n"
        f"PUBLISHED_AT: {published_at}\n"
        f"SUMMARY: {raw_summary}\n\n"
        f"FULL_TEXT:\n{compressed}\n"
    )
    if clean_discussion:
        prompt += f"\nDISCUSSION CONTEXT:\n{clean_discussion}\n"
    return prompt


class ProfileRouter:
    PROFILES_DIR = Path(__file__).resolve().parent / "prompts" / "profiles"

    def __init__(self, base_prompt: str, config: Optional[Dict[str, Any]] = None):
        self.base_prompt = base_prompt
        self.config = config or {}
        self._cache: Dict[str, str] = {}
        self._source_profiles: Dict[str, str] = {}
        for src in self.config.get("sources", []):
            if isinstance(src, dict) and src.get("id") and src.get("profile"):
                self._source_profiles[src["id"]] = src["profile"]

    def _load_rubric(self, profile_name: str) -> str:
        if profile_name in self._cache:
            return self._cache[profile_name]
        path = self.PROFILES_DIR / f"{profile_name}.txt"
        if path.exists():
            rubric = path.read_text(encoding="utf-8").strip()
        else:
            rubric = ""
        self._cache[profile_name] = rubric
        return rubric

    def resolve_profile(self, source_id: str, url: str, title: str) -> str:
        if source_id in self._source_profiles:
            return self._source_profiles[source_id]

        url_lower = (url or "").lower()
        title_lower = (title or "").lower()

        if re.search(r"arxiv\.org|biorxiv\.org|openreview\.net", url_lower) or "paper" in title_lower:
            return "research_paper"

        if (
            re.search(r"huggingface\.co", url_lower)
            or re.search(r"github\.com/[^/]+/[^/]+/(releases|tags)", url_lower)
            or re.search(r"release[_-]?notes|help\.openai\.com", url_lower)
            or any(kw in title_lower for kw in ("release", "выпустила", "представила", "weights", "weights available", "llama", "deepseek", "qwen", "gemma", "claude", "gpt-", "mistral"))
        ):
            return "model_release"

        if re.search(r"github\.com", url_lower):
            return "tool_or_code"

        if re.search(r"news\.ycombinator\.com|reddit\.com", url_lower):
            return "community_discussion"

        return "industry_news"

    def get_prompt(self, profile_name: str) -> str:
        rubric = self._load_rubric(profile_name)
        if "{PROFILE_RUBRIC}" in self.base_prompt:
            return self.base_prompt.replace("{PROFILE_RUBRIC}", rubric)
        elif rubric:
            return f"{self.base_prompt}\n\n{rubric}"
        return self.base_prompt


def analyze(
    db_path: str,
    prompt_path: Path,
    limit: int,
    logger: logging.Logger,
    source_ids: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    base_prompt = read_prompt(prompt_path)
    router = ProfileRouter(base_prompt, config)
    client = HybridLLMClient(logger)

    budget = calculate_vram_budget(LOCAL_MODEL_PARAMS_B, LOCAL_MODEL_QUANT, LOCAL_MODEL_N_CTX)
    logger.info("vram_budget=%s", budget)

    updated = 0
    with sqlite3.connect(db_path) as conn:
        rows = fetch_pending_priority(conn, limit, source_ids)
        if not rows:
            logger.warning("No pending items found.")
            return 0

        for row in rows:
            item_id, source_id, url, title, published_at, raw_summary, full_text, discussion_context = row
            if not full_text:
                continue
            profile = router.resolve_profile(source_id=source_id, url=url, title=title or "")
            item_prompt = router.get_prompt(profile)
            before_len = len(full_text)
            user_prompt = build_user_prompt(
                source_id=source_id,
                url=url,
                title=title or "",
                published_at=published_at or "",
                raw_summary=raw_summary or "",
                full_text=trim_text(full_text, MAX_INPUT_CHARS),
                discussion_context=discussion_context,
            )
            after_len = len(user_prompt)
            logger.debug("context_compress url=%s raw_len=%s prompt_len=%s profile=%s", url, before_len, after_len, profile)
            try:
                response = client.generate(item_prompt, user_prompt)
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
            formatted_rationale = format_impact_rationale(rationale_raw, max_chars=320, max_sentences=3)

            raw_action_items = normalize_list(parsed.get("action_items"))
            cleaned_actions: List[str] = []
            for item in raw_action_items:
                act = clean_action_item(item, 140)
                if act:
                    cleaned_actions.append(act)
            cleaned_actions = cleaned_actions[:MAX_ACTION_ITEMS]

            tags = normalize_list(parsed.get("tags"))
            tags = [strip_citation_brackets(sanitize_text(tag, 40)) for tag in tags if sanitize_text(tag, 40)][:8]
            tags = [t for t in tags if t]

            entities = normalize_list(parsed.get("entities"))
            entities = [strip_citation_brackets(sanitize_text(ent, 60)) for ent in entities if sanitize_text(ent, 60)][:8]
            entities = [e for e in entities if e]

            payload = {
                "impact_score": normalize_score(parsed.get("impact_score")),
                "target_role": str(parsed.get("target_role") or "other").strip() or "other",
                "impact_rationale": formatted_rationale,
                "action_items": cleaned_actions,
                "tags": tags,
                "entities": entities,
                "confidence": normalize_confidence(parsed.get("confidence")),
            }

            if not validate_payload(payload, logger, url):
                continue

            update_item(conn, item_id, payload, content_profile=profile)
            updated += 1
            if updated % ANALYZER_COMMIT_INTERVAL == 0:
                conn.commit()
            if LLM_THROTTLE_SECONDS > 0:
                time.sleep(LLM_THROTTLE_SECONDS)

        conn.commit()

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze news items with LLM.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_DB_CONFIG_PATH),
        help="Path to config.yaml",
    )
    parser.add_argument("--limit", type=int, default=MAX_ITEMS_PER_RUN)
    parser.add_argument(
        "--source-id",
        default="",
        help="Optional comma-separated source ids for targeted analysis.",
    )
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

    source_ids = [part.strip() for part in args.source_id.split(",") if part.strip()]
    if source_ids:
        logger.warning("Running targeted analysis for source_ids=%s", ",".join(source_ids))

    updated = analyze(db_path, prompt_path, args.limit, logger, source_ids or None, config=config)
    logger.warning("Updated items: %s", updated)


if __name__ == "__main__":
    main()
