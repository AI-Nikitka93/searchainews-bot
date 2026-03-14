import os
import sqlite3
from pathlib import Path


def ensure_db_dir(db_path: str) -> None:
    directory = Path(db_path).parent
    if directory and not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: str) -> sqlite3.Connection:
    ensure_db_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
