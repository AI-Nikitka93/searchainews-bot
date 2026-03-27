import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import requests


def load_env(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("\"").strip("'")
    return data


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def run_command(args: list[str], cwd: Optional[Path] = None) -> Optional[str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        return stderr or stdout or None
    return (completed.stdout or "").strip() or None


def print_pipeline_status(root: Path) -> None:
    if not shutil.which("gh"):
        print("pipeline: gh CLI not found")
        return

    repo = run_command(["git", "remote", "get-url", "origin"], cwd=root)
    if not repo:
        print("pipeline: git remote not found")
        return

    latest = run_command(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            "pipeline.yml",
            "--limit",
            "1",
            "--json",
            "databaseId,conclusion,status,event,createdAt,updatedAt,url",
        ],
        cwd=root,
    )
    if not latest:
        print("pipeline: no workflow data")
        return

    try:
        import json

        runs = json.loads(latest)
    except Exception:
        print("pipeline: failed to parse workflow data")
        return

    if not runs:
        print("pipeline: no runs found")
        return

    run = runs[0]
    run_id = str(run.get("databaseId") or "")
    print(
        "pipeline latest:",
        f"status={run.get('status')}",
        f"conclusion={run.get('conclusion')}",
        f"event={run.get('event')}",
        f"created_at={run.get('createdAt')}",
    )
    if run.get("url"):
        print(f"pipeline url: {run['url']}")

    if not run_id:
        return

    details = run_command(
        ["gh", "run", "view", run_id, "--json", "jobs"],
        cwd=root,
    )
    if not details:
        return

    try:
        import json

        payload = json.loads(details)
    except Exception:
        return

    jobs = payload.get("jobs") or []
    for job in jobs[:3]:
        print(
            "pipeline job:",
            f"name={job.get('name')}",
            f"status={job.get('status')}",
            f"conclusion={job.get('conclusion')}",
        )

    human_view = run_command(["gh", "run", "view", run_id], cwd=root)
    if human_view:
        annotations = []
        capture = False
        for line in human_view.splitlines():
            if line.strip() == "ANNOTATIONS":
                capture = True
                continue
            if capture:
                if not line.strip():
                    continue
                annotations.append(line.strip())
        if annotations:
            print("pipeline annotations:")
            for line in annotations[:5]:
                print(f"  {line}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")

    bot_token = env.get("BOT_TOKEN", "")
    webhook_secret = env.get("WEBHOOK_SECRET", "")
    ingest_secret = env.get("INGEST_SECRET", "")
    webhook_url = env.get("WEBHOOK_URL", "")

    print("=== DIAG BOT ===")
    print(f"BOT_TOKEN: {'yes' if bot_token else 'no'} ({mask(bot_token)})")
    print(f"WEBHOOK_SECRET: {'yes' if webhook_secret else 'no'} ({mask(webhook_secret)})")
    print(f"INGEST_SECRET: {'yes' if ingest_secret else 'no'} ({mask(ingest_secret)})")

    if not bot_token:
        print("ERROR: BOT_TOKEN missing in .env")
        return 1

    base = f"https://api.telegram.org/bot{bot_token}"
    try:
        me = requests.get(f"{base}/getMe", timeout=20).json()
        print(f"getMe ok: {me.get('ok')} username: {me.get('result', {}).get('username')}")
    except Exception as exc:
        print(f"getMe failed: {exc}")
        return 1

    try:
        info = requests.get(f"{base}/getWebhookInfo", timeout=20).json()
        print(f"getWebhookInfo ok: {info.get('ok')}")
        result = info.get("result", {}) or {}
        print(f"webhook url: {result.get('url')}")
        print(f"allowed_updates: {result.get('allowed_updates')}")
        print(f"pending_update_count: {result.get('pending_update_count')}")
        print(f"last_error_message: {result.get('last_error_message')}")
        print(f"last_error_date: {result.get('last_error_date')}")
    except Exception as exc:
        print(f"getWebhookInfo failed: {exc}")
        return 1

    effective_webhook = webhook_url or (info.get("result", {}) or {}).get("url", "")
    if effective_webhook:
        base_worker = effective_webhook.split("/webhook")[0]
        health_url = f"{base_worker}/health"
        try:
            health = requests.get(health_url, timeout=20)
            print(f"worker /health: {health.status_code}")
        except Exception as exc:
            print(f"worker /health failed: {exc}")

        if webhook_secret:
            debug_url = f"{base_worker}/webhook/{webhook_secret}"
            try:
                debug = requests.post(
                    debug_url,
                    headers={"X-Debug-Token": ingest_secret or webhook_secret},
                    json={"ok": True},
                    timeout=20,
                )
                print(f"debug webhook status: {debug.status_code}")
                if debug.headers.get("content-type", "").startswith("application/json"):
                    print(f"debug payload: {debug.json()}")
            except Exception as exc:
                print(f"debug webhook failed: {exc}")

            try:
                probe = requests.post(debug_url, json={"update_id": 1}, timeout=20)
                print(f"webhook probe status (no header): {probe.status_code}")
            except Exception as exc:
                print(f"webhook probe failed: {exc}")

    print_pipeline_status(root)

    print("=== END ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
