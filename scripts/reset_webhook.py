import os
from pathlib import Path
from typing import Dict

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


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")
    bot_token = env.get("BOT_TOKEN", "")
    webhook_secret = env.get("WEBHOOK_SECRET", "")
    webhook_url_env = env.get("WEBHOOK_URL", "")

    if not bot_token or not webhook_secret:
        print("BOT_TOKEN or WEBHOOK_SECRET missing in .env")
        return 1

    base = f"https://api.telegram.org/bot{bot_token}"
    info = requests.get(f"{base}/getWebhookInfo", timeout=20).json()
    current_url = (info.get("result", {}) or {}).get("url", "")
    target_url = webhook_url_env or current_url
    if not target_url:
        print("Webhook URL not found (set WEBHOOK_URL in .env).")
        return 1

    print(f"Current webhook: {current_url}")
    print(f"Target webhook: {target_url}")

    payload = {
        "url": target_url,
        "secret_token": webhook_secret,
        "drop_pending_updates": True,
    }
    resp = requests.post(f"{base}/setWebhook", json=payload, timeout=20).json()
    print(f"setWebhook ok: {resp.get('ok')} description: {resp.get('description')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
