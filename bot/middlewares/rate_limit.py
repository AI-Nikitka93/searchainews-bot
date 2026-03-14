import time
from typing import Dict, List

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import CancelHandler
from aiogram.types import TelegramObject

from bot.config import RATE_LIMIT_BURST, RATE_LIMIT_PER_SECONDS


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.calls: Dict[int, List[float]] = {}

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        now = time.monotonic()
        window = RATE_LIMIT_PER_SECONDS
        history = [t for t in self.calls.get(user.id, []) if now - t <= window]
        if len(history) >= RATE_LIMIT_BURST:
            raise CancelHandler()

        history.append(now)
        self.calls[user.id] = history
        return await handler(event, data)
