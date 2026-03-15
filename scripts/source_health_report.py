import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

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


def build_report(state: Dict[str, Any]) -> str:
    if not state:
        return "Source health: no state yet."

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
        return summary + "\nAll sources healthy."
    return summary + "\n" + "\n".join(rows)


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
    report = build_report(state)
    return send_telegram(report)


if __name__ == "__main__":
    raise SystemExit(main())
