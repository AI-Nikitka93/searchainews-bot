import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import requests

DEFAULT_FAIL_THRESHOLD = 3
DEFAULT_ALERT_COOLDOWN_HOURS = 24
DEFAULT_MIN_REPORT_INTERVAL_MINUTES = 180


def get_state_path() -> Path:
    env_dir = os.environ.get("LOCALAPPDATA")
    if env_dir:
        base = Path(env_dir)
    else:
        import tempfile
        expanded = os.path.expandvars(r"%LOCALAPPDATA%")
        base = Path(tempfile.gettempdir()) if expanded == "%LOCALAPPDATA%" else Path(expanded)
    return base / "SearchAInews" / "state" / "source_state.json"


def load_state() -> Dict[str, Any]:
    path = get_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    path = get_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def is_in_cooldown(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    disabled_until = data.get("disabled_until")
    if not disabled_until:
        return False, None
    try:
        dt = datetime.fromisoformat(disabled_until)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now < dt:
            delta = dt - now
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            remaining = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            return True, remaining
    except ValueError:
        pass
    return False, None


def format_age(ts: Optional[str]) -> str:
    if not ts:
        return "never"
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return "unknown"
    now = datetime.now(timezone.utc)
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    hours = int(delta.total_seconds() // 3600)
    if hours >= 48:
        return f"{hours // 24}d ago"
    if hours >= 1:
        return f"{hours}h ago"
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes}m ago"


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


def clean_error_message(err: Optional[str], max_len: int = 100) -> str:
    if not err:
        return "unknown error"
    err_str = str(err).strip()
    if len(err_str) > max_len:
        return err_str[:max_len] + "..."
    return err_str


def compute_health_score(data: Dict[str, Any]) -> int:
    fail_count = int(data.get("fail_count", 0))
    last_success = data.get("last_success_ts")
    last_items = data.get("last_items")
    in_cd, _ = is_in_cooldown(data)

    if not last_success:
        if fail_count == 0:
            return 80  # provisional neutral score for newly registered source
        return max(0, 50 - fail_count * 20)

    score = 100
    score -= min(fail_count * 25, 75)
    try:
        dt = datetime.fromisoformat(last_success)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = int((datetime.now(timezone.utc) - dt).total_seconds() // 3600)
        if hours > 48:
            score -= min((hours - 48) // 4, 30)
    except ValueError:
        pass

    if last_items == 0 and fail_count > 0:
        score -= 10
    if in_cd:
        score = min(score, 30)
    return max(score, 0)


def evaluate_sources(state: Dict[str, Any], fail_threshold: int = DEFAULT_FAIL_THRESHOLD) -> Dict[str, Any]:
    sources = {k: v for k, v in state.items() if not k.startswith("_")}
    persistent_failures = []
    cooldown_sources = []
    transient_failures = []
    recovered_sources = []
    healthy_count = 0

    for source_id, data in sources.items():
        fail_count = int(data.get("fail_count", 0))
        last_error = data.get("last_error")
        last_success = data.get("last_success_ts")
        last_items = data.get("last_items")
        last_alert_ts = data.get("last_alert_ts")
        in_cd, cd_remaining = is_in_cooldown(data)
        score = compute_health_score(data)

        if fail_count == 0 and last_alert_ts:
            recovered_sources.append({
                "id": source_id,
                "last_success": last_success,
            })

        if in_cd:
            cooldown_sources.append({
                "id": source_id,
                "remaining": cd_remaining,
                "error": last_error,
                "fail_count": fail_count,
                "score": score,
                "last_success": last_success,
                "disabled_until": data.get("disabled_until"),
            })
        elif fail_count >= fail_threshold:
            persistent_failures.append({
                "id": source_id,
                "fail_count": fail_count,
                "error": last_error,
                "score": score,
                "last_success": last_success,
                "last_items": last_items,
                "last_alert_ts": last_alert_ts,
                "last_alert_fail_count": data.get("last_alert_fail_count", 0),
            })
        elif fail_count > 0:
            transient_failures.append({
                "id": source_id,
                "fail_count": fail_count,
                "error": last_error,
                "score": score,
                "last_success": last_success,
            })
        else:
            healthy_count += 1

    persistent_failures.sort(key=lambda x: (-x["fail_count"], x["id"]))
    cooldown_sources.sort(key=lambda x: x["id"])

    return {
        "total": len(sources),
        "healthy_count": healthy_count,
        "persistent_failures": persistent_failures,
        "cooldown_sources": cooldown_sources,
        "transient_failures": transient_failures,
        "recovered_sources": recovered_sources,
    }


def parse_env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


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


def check_alert_eligibility(
    eval_result: Dict[str, Any],
    state: Dict[str, Any],
    fail_threshold: int,
    alert_cooldown_hours: int,
    min_report_interval_minutes: int,
) -> Tuple[bool, List[str], str]:
    now = datetime.now(timezone.utc)
    meta = state.get("_meta", {})
    last_report_sent_ts = meta.get("last_report_sent_ts")

    hours_raw = os.getenv("HEALTH_REPORT_UTC_HOURS", "").strip()
    if hours_raw:
        allowed_hours = parse_hours(hours_raw)
        if allowed_hours and now.hour not in allowed_hours:
            return False, [], "Current UTC hour not in allowed HEALTH_REPORT_UTC_HOURS."

    if last_report_sent_ts:
        try:
            dt = datetime.fromisoformat(last_report_sent_ts)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            if now - dt < timedelta(minutes=min_report_interval_minutes):
                has_new_unalerted = any(not s.get("last_alert_ts") for s in eval_result["persistent_failures"])
                if not has_new_unalerted:
                    mins_ago = int((now - dt).total_seconds() // 60)
                    return False, [], f"Report throttled (sent {mins_ago}m ago, min interval {min_report_interval_minutes}m)."
        except ValueError:
            pass

    sources_to_alert: List[str] = []
    for s in eval_result["persistent_failures"]:
        last_alert = s.get("last_alert_ts")
        if not last_alert:
            sources_to_alert.append(s["id"])
        else:
            try:
                dt = datetime.fromisoformat(last_alert)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                last_fail_cnt = int(s.get("last_alert_fail_count", 0))
                if (now - dt >= timedelta(hours=alert_cooldown_hours)) or (s["fail_count"] - last_fail_cnt >= 10):
                    sources_to_alert.append(s["id"])
            except ValueError:
                sources_to_alert.append(s["id"])

    only_on_failure = parse_env_bool("HEALTH_REPORT_ONLY_ON_FAILURE", default=True)
    min_failing_raw = os.getenv("HEALTH_REPORT_MIN_FAILING", "").strip()
    min_failing = int(min_failing_raw) if min_failing_raw.isdigit() else 1

    persistent_count = len(eval_result["persistent_failures"])
    recovered_count = len(eval_result["recovered_sources"])

    if only_on_failure:
        if persistent_count == 0 and recovered_count == 0:
            return False, [], "All sources healthy; failure-only filter active."
        if persistent_count < min_failing and recovered_count == 0:
            return False, [], f"Persistent failing count ({persistent_count}) below minimum threshold ({min_failing})."
        if not sources_to_alert and recovered_count == 0:
            return False, [], "Persistent failures already alerted within cooldown cycle."

    return True, sources_to_alert, "Alert criteria met."


def build_report_message(eval_result: Dict[str, Any], sources_to_alert: List[str]) -> str:
    total = eval_result["total"]
    healthy = eval_result["healthy_count"]
    persistent = eval_result["persistent_failures"]
    cooldowns = eval_result["cooldown_sources"]
    transients = eval_result["transient_failures"]
    recovered = eval_result["recovered_sources"]

    lines = []
    if persistent:
        lines.append(f"🚨 Source Health Alert: {len(persistent)} Persistent Outage{'s' if len(persistent) > 1 else ''}")
    elif cooldowns:
        lines.append(f"⚠️ Source Health: {len(cooldowns)} Quarantined Source{'s' if len(cooldowns) > 1 else ''}")
    else:
        lines.append(f"✅ Source Health: All {total} sources operational")

    lines.append(f"Total: {total} | Healthy: {healthy} | Critical: {len(persistent)} | Cooldown: {len(cooldowns)} | Transient: {len(transients)}")

    if persistent:
        lines.append("\n❌ Persistent Failures (>= 3 consecutive runs):")
        for s in persistent[:8]:
            age = format_age(s["last_success"])
            err = clean_error_message(s["error"])
            new_tag = " [NEW OUTAGE]" if s["id"] in sources_to_alert else ""
            lines.append(f"- {s['id']}: fails={s['fail_count']} ok={age}{new_tag}\n  Error: {err}")

    if cooldowns:
        lines.append("\n⏸️ Quarantined (Auto-Backoff):")
        for c in cooldowns[:6]:
            err = clean_error_message(c["error"], max_len=75)
            lines.append(f"- {c['id']}: backoff for {c['remaining']}\n  Reason: {err}")

    if recovered:
        lines.append("\n✅ Recovered Sources:")
        for r in recovered[:5]:
            lines.append(f"- {r['id']}: restored and fetching successfully")

    if transients:
        lines.append(f"\nℹ️ Transient 1-off errors suppressed from alert: {len(transients)}")

    return "\n".join(lines)


def build_report(state: Dict[str, Any]) -> Tuple[str, int]:
    """Backwards-compatible report builder."""
    eval_result = evaluate_sources(state)
    persistent = eval_result["persistent_failures"]
    report = build_report_message(eval_result, [s["id"] for s in persistent])
    return report, len(persistent)


def should_send(failing_count: int) -> bool:
    """Backwards-compatible should_send check."""
    if parse_env_bool("HEALTH_REPORT_ONLY_ON_FAILURE", default=True) and failing_count == 0:
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
    if chat_id.startswith("-"):
        print(f"Refusing to send administrative health report to non-private chat_id: {chat_id}")
        return 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code >= 300:
            print(f"Health report failed: {resp.status_code} {resp.text}")
            return 1
    except requests.RequestException as e:
        print(f"Network error sending health report: {e}")
        return 1
    print("Health report sent.")
    return 0


def main() -> int:
    state = load_state()
    fail_threshold_raw = os.getenv("HEALTH_REPORT_FAIL_THRESHOLD", "").strip()
    fail_threshold = int(fail_threshold_raw) if fail_threshold_raw.isdigit() else DEFAULT_FAIL_THRESHOLD

    alert_cooldown_raw = os.getenv("HEALTH_REPORT_ALERT_COOLDOWN_HOURS", "").strip()
    alert_cooldown_hours = int(alert_cooldown_raw) if alert_cooldown_raw.isdigit() else DEFAULT_ALERT_COOLDOWN_HOURS

    min_interval_raw = os.getenv("HEALTH_REPORT_MIN_INTERVAL_MINUTES", "").strip()
    min_interval_minutes = int(min_interval_raw) if min_interval_raw.isdigit() else DEFAULT_MIN_REPORT_INTERVAL_MINUTES

    eval_result = evaluate_sources(state, fail_threshold=fail_threshold)
    should_send_report, sources_to_alert, reason = check_alert_eligibility(
        eval_result,
        state,
        fail_threshold=fail_threshold,
        alert_cooldown_hours=alert_cooldown_hours,
        min_report_interval_minutes=min_interval_minutes,
    )

    report_text = build_report_message(eval_result, sources_to_alert)
    print("=== Source Health Status ===")
    print(f"Total: {eval_result['total']} | Critical: {len(eval_result['persistent_failures'])} | Cooldown: {len(eval_result['cooldown_sources'])} | Transient: {len(eval_result['transient_failures'])}")
    print(f"Eligibility: {reason}")

    if not should_send_report:
        print("Health report suppressed by policy.")
        if eval_result["recovered_sources"]:
            for r in eval_result["recovered_sources"]:
                if r["id"] in state:
                    state[r["id"]].pop("last_alert_ts", None)
                    state[r["id"]].pop("last_alert_fail_count", None)
            save_state(state)
        return 0

    exit_code = send_telegram(report_text)
    if exit_code == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        for s_id in sources_to_alert:
            if s_id in state:
                state[s_id]["last_alert_ts"] = now_iso
                state[s_id]["last_alert_fail_count"] = state[s_id].get("fail_count", 0)
        for r in eval_result["recovered_sources"]:
            if r["id"] in state:
                state[r["id"]].pop("last_alert_ts", None)
                state[r["id"]].pop("last_alert_fail_count", None)
        state.setdefault("_meta", {})
        state["_meta"]["last_report_sent_ts"] = now_iso
        save_state(state)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
