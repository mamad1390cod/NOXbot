"""Throttling middleware to prevent spam."""

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types


class ThrottlingMiddleware(BaseMiddleware):
    """Simple rate limiter per user per chat.

    Users sending more than ``rate_limit`` messages within ``time_window``
    seconds get throttled (updates dropped silently). This protects the bot
    from spam and flood.
    """

    def __init__(self, rate_limit: int = 5, time_window: float = 3.0) -> None:
        self.rate_limit = rate_limit
        self.time_window = time_window
        self._records: dict[str, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None and hasattr(event, "from_user"):
            user = event.from_user
        if user is None:
            # Messages without a user (e.g. channel posts) bypass throttling.
            return await handler(event, data)

        key = str(user.id)
        now = time.time()
        records = [t for t in self._records[key] if now - t <= self.time_window]
        self._records[key] = records

        if len(records) >= self.rate_limit:
            # Drop the event silently (rate-limited).
            return None

        self._records[key].append(now)
        return await handler(event, data)