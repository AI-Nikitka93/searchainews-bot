from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.config import ROLE_OPTIONS
from bot.database.sqlite import get_connection
from bot.services.user_service import set_role
from bot.keyboards.role import role_keyboard
from bot.config import get_db_path

router = Router()

ROLE_SET = {key for key, _ in ROLE_OPTIONS}


@router.callback_query(F.data.startswith("role:"))
async def role_handler(query: CallbackQuery) -> None:
    role = query.data.split(":", 1)[-1]
    if role not in ROLE_SET:
        await query.answer("Unknown role", show_alert=True)
        return

    db_path = get_db_path()
    with get_connection(db_path) as conn:
        set_role(conn, query.from_user.id, role)

    await query.answer("Role saved")
    await query.message.edit_text(
        f"Role updated: {role.upper()}\nUse /latest to get the latest actionable news.",
        reply_markup=role_keyboard(),
    )
