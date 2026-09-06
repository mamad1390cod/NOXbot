"""Maintenance-mode middleware — blocks non-admins when maintenance is on."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types
from aiogram.types import TelegramObject

from bot.services.features import Feature
from bot.services.rbac import RbacService
from bot.services.settings import SettingsService

logger = logging.getLogger(__name__)


class MaintenanceMiddleware(BaseMiddleware):
    """When maintenance mode is enabled, only admins may interact.

    Runs after UserContextMiddleware (so ``data["user"]``/``data["uow"]`` are
    present). Non-admin updates are answered with the maintenance message and
    dropped.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        uow = data.get("uow")
        if user is None or uow is None:
            return await handler(event, data)

        try:
            settings = SettingsService(uow)
            if await settings.feature_enabled(Feature.MAINTENANCE_MODE):
                # Admins (owner or ACTIVE AdminProfile) bypass maintenance.
                rbac = RbacService(uow)
                if not await rbac.is_admin(user):
                    msg = await settings.t("maintenance_message")
                    # Determine the correct reply target.
                    reply_target = None
                    if isinstance(event, types.Message):
                        reply_target = event
                    elif isinstance(event, types.CallbackQuery) and event.message:
                        reply_target = event.message
                    if reply_target is not None:
                        try:
                            await reply_target.answer(msg, parse_mode="HTML")
                        except Exception as e:
                            logger.debug("maintenance ack failed: %s", e)
                    return None  # drop the update
        except Exception as e:
            logger.exception("MaintenanceMiddleware error: %s", e)

        return await handler(event, data)