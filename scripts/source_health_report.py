import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple

import requests


def load_state() -> Dict[str, Any]:
    base = Path(os.path.expandvars(r"%LOCALAPPDATA%"))
    path = base / "SearchAInews" / "state" / "source_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def format_age(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return "unknown"
    now = datetime.now(timezone.utc)
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    hours = int(delta.total_seconds() // 3600)
    return f"{hours}h"


def age_hours(ts: str) -> int:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return 0
    now = datetime.now(timezone.utc)
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    return int(delta.total_seconds() // 3600)


def compute_health_score(data: Dict[str, Any]) -> int:
    fail_count = int(data.get("fail_count", 0))
    last_success = data.get("last_success_ts")
    last_items = data.get("last_items")
    disabled_until = data.get("disabled_until")

    if not last_success:
        return 0

    score = 100
    score -= min(fail_count * 20, 80)
    score -= min(age_hours(last_success), 72)
    if last_items == 0:
        score -= 10
    if disabled_until:
        score = min(score, 20)
    return max(score, 0)


def build_report(state: Dict[str, Any]) -> Tuple[str, int]:
    if not state:
        return "Source health: no state yet.", 0

    rows: List[str] = []
    failing = []
    for source_id, data in state.items():
        fail_count = int(data.get("fail_count", 0))
        last_error = data.get("last_error")
        last_success = data.get("last_success_ts")
        last_items = data.get("last_items")
        disabled_until = data.get("disabled_until")
        health_score = compute_health_score(data)
        if fail_count > 0 or last_error or health_score <= 60:
            failing.append(
                (source_id, fail_count, last_success, last_error, last_items, disabled_until, health_score)
            )

    failing.sort(key=lambda x: (-x[1], x[0]))
    for source_id, fail_count, last_success, last_error, last_items, disabled_until, health_score in failing[:10]:
        age = format_age(last_success) if last_success else "never"
        disabled = f" disabled_until={disabled_until}" if disabled_until else ""
        err = f" err={str(last_error)[:90]}" if last_error else ""
        rows.append(
            f"- {source_id}: score={health_score} fail={fail_count} last_ok={age} items={last_items}{disabled}{err}"
        )

    summary = f"Source health: total={len(state)} failing={len(failing)}"
    if not rows:
        return summary + "\nAll sources healthy.", len(failing)
    return summary + "\n" + "\n".join(rows), len(failing)


def parse_env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def parse_hours(value: str) -> List[int]:
    hours: List[int] = []
    for raw in value.split(","):
        part = raw.strip()
        if not part:
            continue
        try:
            hour = int(part)
        except ValueError:
            continue
        if 0 <= hour <= 23:
            hours.append(hour)
    return sorted(set(hours))


def should_send(failing_count: int) -> bool:
    if parse_env_bool("HEALTH_REPORT_ONLY_ON_FAILURE") and failing_count == 0:
        return False
    min_failing_raw = os.getenv("HEALTH_REPORT_MIN_FAILING", "").strip()
    if min_failing_raw:
        try:
            min_failing = int(min_failing_raw)
        except ValueError:
            min_failing = 0
        if min_failing > 0 and failing_count < min_failing:
            return False
    hours_raw = os.getenv("HEALTH_REPORT_UTC_HOURS", "").strip()
    if hours_raw:
        allowed_hours = parse_hours(hours_raw)
        if allowed_hours and datetime.now(timezone.utc).hour not in allowed_hours:
            return False
    return True


def send_telegram(message: str) -> int:
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("BOT_TOKEN or ADMIN_CHAT_ID missing; skip health report.")
        return 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code >= 300:
        print(f"Health report failed: {resp.status_code} {resp.text}")
        return 1
    print("Health report sent.")
    return 0


def main() -> int:
    state = load_state()
    report, failing_count = build_report(state)
    if not should_send(failing_count):
        print("Health report suppressed by policy.")
        return 0
    return send_telegram(report)


if __name__ == "__main__":
    raise SystemExit(main())
