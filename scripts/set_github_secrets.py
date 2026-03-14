import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict

import requests
from nacl import public

ROOT = Path(__file__).resolve().parents[1]


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


def encrypt_secret(public_key: str, secret_value: str) -> str:
    key = public.PublicKey(public_key.encode("utf-8"), encoder=public.Base64Encoder())
    sealed_box = public.SealedBox(key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/set_github_secrets.py <owner> <repo>")
        return 1

    owner = sys.argv[1]
    repo = sys.argv[2]
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN is missing.")
        return 1

    env = load_env(ROOT / ".env")
    secrets = {
        "INGEST_URL": env.get("INGEST_URL", ""),
        "INGEST_SECRET": env.get("INGEST_SECRET", ""),
        "OPENROUTER_API_KEY": env.get("OPENROUTER_API_KEY", ""),
    }

    missing = [k for k, v in secrets.items() if not v]
    if missing:
        print(f"Missing secrets in .env: {', '.join(missing)}")
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "searchainews-setup",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    key_resp = requests.get(key_url, headers=headers, timeout=20)
    key_resp.raise_for_status()
    key_payload = key_resp.json()
    key_id = key_payload["key_id"]
    public_key = key_payload["key"]

    for name, value in secrets.items():
        encrypted_value = encrypt_secret(public_key, value)
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id,
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{name}"
        resp = requests.put(url, headers=headers, data=json.dumps(payload), timeout=20)
        resp.raise_for_status()
        print(f"Secret set: {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
