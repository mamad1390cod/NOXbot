"""RBAC middleware — injects the effective permission set into handler data.

Runs after UserContextMiddleware (so ``data["user"]`` and ``data["uow"]`` are
available) and populates ``data["permissions"]`` so handlers can render
permission-aware keyboards without re-querying the DB.
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types
from aiogram.types import TelegramObject

from bot.services.rbac import RbacService

logger = logging.getLogger(__name__)


class RbacMiddleware(BaseMiddleware):
    """Populate data['permissions'] with the caller's effective permission set."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        uow = data.get("uow")
        if user is not None and uow is not None:
            try:
                rbac = RbacService(uow)
                data["permissions"] = await rbac.effective_permissions(user)
            except Exception as e:
                logger.exception("RbacMiddleware error: %s", e)
                data["permissions"] = set()
        else:
            data["permissions"] = set()
        return await handler(event, data)