"""User-related filters."""

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


class IsBanned(BaseFilter):
    """Filter that matches banned users (for blocking them early).

    Note: This is a placeholder; actual ban checking happens in the
    middleware where we have DB access. Kept for handler-level clarity.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        # Ban state checked in middleware; here we assume not banned.
        return False