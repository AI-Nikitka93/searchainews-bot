from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.sqlite import get_connection
from bot.keyboards.role import role_keyboard
from bot.services.news_service import get_latest_for_role
from bot.services.user_service import get_user_role
from bot.utils.text import format_news_item
from bot.config import get_db_path

router = Router()


@router.message(Command("latest"))
async def latest_handler(message: Message) -> None:
    db_path = get_db_path()
    with get_connection(db_path) as conn:
        role = get_user_role(conn, message.from_user.id)
        if not role:
            await message.answer("Pick a role first:", reply_markup=role_keyboard())
            return
        items = get_latest_for_role(conn, role, limit=3)

    if not items:
        await message.answer("No news for your role yet. Try later.")
        return

    for item in items:
        await message.answer(format_news_item(item))
