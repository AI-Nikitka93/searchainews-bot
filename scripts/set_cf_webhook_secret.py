import os
import subprocess
from pathlib import Path
from typing import Dict


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
    secret = env.get("WEBHOOK_SECRET", "")
    if not secret:
        print("WEBHOOK_SECRET missing in .env")
        return 1

    worker_dir = root / "cf_worker"
    wrangler_cmd = worker_dir / "node_modules" / ".bin" / "wrangler.cmd"
    if not wrangler_cmd.exists():
        print("wrangler.cmd not found in cf_worker/node_modules/.bin")
        return 1
    cmd = [str(wrangler_cmd), "secret", "put", "WEBHOOK_SECRET"]
    try:
        subprocess.run(
            cmd,
            cwd=str(worker_dir),
            input=secret,
            text=True,
            check=True,
        )
        print("Cloudflare WEBHOOK_SECRET updated.")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Failed to update WEBHOOK_SECRET: {exc}")
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
