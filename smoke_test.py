import os
import sqlite3
from typing import Tuple

from scraper import run_scraper


def get_db_path(config_path: str) -> str:
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return os.path.expandvars(config["db_path"])


def count_items(db_path: str) -> Tuple[int, int]:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM items;")
        total = int(cur.fetchone()[0])
        cur = conn.execute(
            "SELECT COUNT(*) FROM items WHERE full_text IS NOT NULL;"
        )
        enriched = int(cur.fetchone()[0])
    return total, enriched


def main() -> None:
    config_path = "config.yaml"
    run_scraper(config_path, smoke_test=True)

    db_path = get_db_path(config_path)
    total, enriched = count_items(db_path)

    if total < 1:
        raise SystemExit("Smoke test failed: no items saved.")

    print(f"Smoke test OK. Items saved: {total}, enriched: {enriched}")


if __name__ == "__main__":
    main()
