import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN, LOG_PATH
from bot.config import get_db_path
from bot.database.migrations import apply_migrations
from bot.database.sqlite import get_connection
from bot.services.news_service import get_unsent_for_user, mark_delivered
from bot.services.user_service import list_subscribers
from bot.utils.logging import setup_logging
from bot.utils.text import format_news_item


async def main() -> None:
    setup_logging(LOG_PATH)
    logger = logging.getLogger("bot")

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing; cannot broadcast")
        raise SystemExit(1)

    db_path = get_db_path()
    apply_migrations(db_path)

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)

    with get_connection(db_path) as conn:
        users = list_subscribers(conn)
        for user_id, role in users:
            items = get_unsent_for_user(conn, user_id, role, limit=3)
            for item in items:
                try:
                    await bot.send_message(user_id, format_news_item(item))
                    mark_delivered(conn, user_id, item["id"])
                    await asyncio.sleep(0.05)
                except Exception as exc:
                    logger.warning("Failed to send to %s: %s", user_id, exc)

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
