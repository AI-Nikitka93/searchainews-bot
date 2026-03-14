import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List

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


def update_env(path: Path, key: str, value: str) -> None:
    lines: List[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[idx] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    env = load_env(env_path)
    bot_token = env.get("BOT_TOKEN", "")
    if not bot_token:
        print("BOT_TOKEN missing in .env")
        return 1

    base = f"https://api.telegram.org/bot{bot_token}"
    info = requests.get(f"{base}/getWebhookInfo", timeout=20).json()
    url = (info.get("result", {}) or {}).get("url", "")
    match = re.search(r"/webhook/([^/?#]+)", url)
    if not match:
        print("Webhook URL does not include /webhook/<secret>.")
        return 1
    secret = match.group(1)

    update_env(env_path, "WEBHOOK_SECRET", secret)
    print("Updated .env WEBHOOK_SECRET from webhook URL.")

    worker_dir = root / "cf_worker"
    wrangler_cmd = worker_dir / "node_modules" / ".bin" / "wrangler.cmd"
    if not wrangler_cmd.exists():
        print("wrangler.cmd not found in cf_worker/node_modules/.bin")
        return 1

    subprocess.run(
        [str(wrangler_cmd), "secret", "put", "WEBHOOK_SECRET"],
        cwd=str(worker_dir),
        input=secret,
        text=True,
        check=True,
    )
    print("Cloudflare WEBHOOK_SECRET updated.")

    payload = {"url": url, "secret_token": secret, "drop_pending_updates": True}
    resp = requests.post(f"{base}/setWebhook", json=payload, timeout=20).json()
    print(f"setWebhook ok: {resp.get('ok')} description: {resp.get('description')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
