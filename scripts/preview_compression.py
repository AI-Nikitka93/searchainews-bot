import argparse
import os
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_analyzer import compress_full_text
from ai_config import MAX_COMPRESSED_CHARS


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview context compression.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    db_path = os.path.expandvars(config.get("db_path", ""))
    if not db_path:
        print("db_path missing in config.yaml")
        return 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT url, title, full_text FROM items WHERE full_text IS NOT NULL ORDER BY published_at DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
    if not rows:
        print("No items found.")
        return 0

    for url, title, full_text in rows:
        original = full_text or ""
        compressed = compress_full_text(original, MAX_COMPRESSED_CHARS)
        print("URL:", url)
        print("TITLE:", title)
        print("ORIGINAL_LEN:", len(original))
        print("COMPRESSED_LEN:", len(compressed))
        print("PREVIEW:", compressed[:600])
        print("----")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
