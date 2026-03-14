import os
import subprocess
from pathlib import Path


def load_token(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("\"").strip("'")
        if key in {"GITHUB_TOKEN", "GH_TOKEN"}:
            return val
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    token = load_token(repo_root / ".env")
    if not token:
        print("ERROR: GITHUB_TOKEN not found in .env")
        return 1

    extra_header = f"AUTHORIZATION: bearer {token}"
    cmd = ["git", "-c", f"http.extraheader={extra_header}", "push", "-u", "origin", "main"]
    try:
        completed = subprocess.run(cmd, cwd=str(repo_root), check=True)
        return completed.returncode
    except subprocess.CalledProcessError as exc:
        print("ERROR: git push failed")
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
