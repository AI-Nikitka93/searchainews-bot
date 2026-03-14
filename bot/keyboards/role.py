from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import ROLE_OPTIONS


def role_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in ROLE_OPTIONS:
        builder.add(InlineKeyboardButton(text=label, callback_data=f"role:{key}"))
    builder.adjust(2)
    return builder.as_markup()
