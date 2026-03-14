import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    worker_dir = root / "cf_worker"
    wrangler_cmd = worker_dir / "node_modules" / ".bin" / "wrangler.cmd"
    if not wrangler_cmd.exists():
        print("wrangler.cmd not found in cf_worker/node_modules/.bin")
        return 1
    try:
        subprocess.run(
            [str(wrangler_cmd), "secret", "put", "ALLOW_WEBHOOK_WITHOUT_SECRET"],
            cwd=str(worker_dir),
            input="true",
            text=True,
            check=True,
        )
        print("Cloudflare ALLOW_WEBHOOK_WITHOUT_SECRET set to true.")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Failed to set ALLOW_WEBHOOK_WITHOUT_SECRET: {exc}")
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
