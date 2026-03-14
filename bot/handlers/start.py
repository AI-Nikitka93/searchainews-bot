from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.config import BOT_WELCOME, ADMIN_USERNAME
from bot.database.sqlite import get_connection
from bot.keyboards.role import role_keyboard
from bot.services.user_service import upsert_user
from bot.config import get_db_path

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    db_path = get_db_path()
    with get_connection(db_path) as conn:
        upsert_user(conn, message.from_user.id, message.from_user.username)
    text = (
        f"{BOT_WELCOME}\n\n"
        "Choose your role to personalize the feed.\n\n"
        f"Создано {ADMIN_USERNAME}"
    )
    await message.answer(text, reply_markup=role_keyboard())
