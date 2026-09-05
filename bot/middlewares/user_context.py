"""User context middleware — registers users, updates activity, blocks bans."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types
from aiogram.types import TelegramObject

from bot.database.uow import UnitOfWork
from bot.services.user import UserService

logger = logging.getLogger(__name__)


class UserContextMiddleware(BaseMiddleware):
    """Ensures every user is registered in DB, updates last activity,
    and blocks banned users.

    Injects ``user`` (the ORM User) and ``uow`` into handler data.
    """

    def __init__(self) -> None:
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_info = getattr(event, "from_user", None)
        if user_info is None:
            return await handler(event, data)

        from bot.database.uow import UnitOfWork as UOW

        uow = UOW()
        try:
            async with uow:
                user_service = UserService(uow)
                user = await user_service.get_or_create_user(
                    telegram_id=user_info.id,
                    username=user_info.username,
                    first_name=user_info.first_name,
                    last_name=user_info.last_name,
                    language_code=getattr(user_info, "language_code", "fa") or "fa",
                )

                # Block banned users from any interaction.
                if user.is_banned:
                    data["user"] = user
                    data["uow"] = uow
                    data["banned"] = True
                    return None

                # Update activity (but not on every single callback to save writes).
                await user_service.update_activity(user.id)

                data["user"] = user
                data["uow"] = uow
                data["banned"] = False
                return await handler(event, data)
        except Exception as e:
            logger.exception("UserContextMiddleware error: %s", e)
            # Never leave the user with a silently dead button: acknowledge the
            # click / message so the spinner stops and the failure is visible.
            await self._notify_failure(event)
            return None

    @staticmethod
    async def _notify_failure(event: TelegramObject) -> None:
        message = "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید."
        try:
            if isinstance(event, types.CallbackQuery):
                await event.answer(message, show_alert=True)
            elif isinstance(event, types.Message):
                await event.answer(message)
        except Exception:  # pragma: no cover - the API call itself failed
            logger.debug("could not deliver the error notice to the user", exc_info=True)