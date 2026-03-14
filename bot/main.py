import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN, LOG_PATH, BOT_NAME
from bot.database.migrations import apply_migrations
from bot.handlers import latest, roles, start
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.utils.logging import setup_logging
from bot.config import get_db_path


async def main() -> None:
    setup_logging(LOG_PATH)
    logger = logging.getLogger("bot")

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing in .env")
        raise SystemExit(1)

    db_path = get_db_path()
    apply_migrations(db_path)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    dp.include_router(start.router)
    dp.include_router(roles.router)
    dp.include_router(latest.router)

    logger.info("Starting bot: %s", BOT_NAME)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
