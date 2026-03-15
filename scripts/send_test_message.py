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
    token = env.get("BOT_TOKEN", "")
    chat_id = env.get("ADMIN_CHAT_ID", "")
    if not token or not chat_id:
        print("BOT_TOKEN or ADMIN_CHAT_ID missing in .env")
        return 1

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": "✅ Test message from bot"}
    resp = requests.post(url, json=payload, timeout=20)
    print(f"sendMessage status: {resp.status_code}")
    if resp.status_code >= 300:
        print(resp.text)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
