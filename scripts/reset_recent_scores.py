import argparse
import os
import sqlite3
from pathlib import Path

import yaml


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset impact_score for recent items.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    db_path = os.path.expandvars(config.get("db_path", ""))
    if not db_path:
        print("db_path missing in config.yaml")
        return 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM items ORDER BY published_at DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
        ids = [row[0] for row in rows]
        if not ids:
            print("No items found.")
            return 0
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"UPDATE items SET impact_score = NULL, impact_rationale = NULL, action_items_json = NULL, target_role = NULL, tags_json = NULL WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()

    print(f"Reset impact_score for {len(ids)} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
