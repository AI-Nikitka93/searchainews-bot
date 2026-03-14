import logging
import sqlite3

from bot.config import BOT_TOKEN, LOG_PATH
from bot.config import get_db_path
from bot.database.migrations import apply_migrations
from bot.utils.logging import setup_logging


def validate() -> int:
    setup_logging(LOG_PATH)
    logger = logging.getLogger("bot")

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing in .env")
        return 1

    db_path = get_db_path()
    apply_migrations(db_path)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT 1 FROM items LIMIT 1")
    except sqlite3.Error as exc:
        logger.error("DB check failed: %s", exc)
        return 1

    logger.info("Validator OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
