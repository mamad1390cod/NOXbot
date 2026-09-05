import logging
"""Settings service — dynamic, DB-backed settings with an in-memory cache.

Every read resolves the current value through an in-process cache that is
warmed at startup and busted on every write, so changes apply instantly
without restarting the bot.

Handlers should use the ``t()`` / ``button()`` helpers (``bot/services/i18n``)
for user-facing text and ``feature_enabled`` for feature toggles.
"""

from typing import Sequence

from bot.config import get_settings
from bot.models.settings import BotSettings
from bot.services.base import BaseService
from bot.services.features import Feature
from bot.services.settings_registry import REGISTRY, spec_for
from bot.database.uow import UnitOfWork

logger = logging.getLogger(__name__)

# Backward-compatible legacy keys
SETTING_CARD_NUMBER = "card_number"
SETTING_CARD_HOLDER = "card_holder"
SETTING_BANK_NAME = "bank_name"
SETTING_SUPPORT_TEXT = "support_text"
SETTING_WELCOME_MESSAGE = "welcome_message"
SETTING_ADMIN_IDS = "admin_ids"


class SettingsService(BaseService):
    """Settings service to read/write bot settings with an in-memory cache."""

    def __init__(self, uow: UnitOfWork) -> None:
        super().__init__(uow)

    # --- Cache ------------------------------------------------------------ #
    async def load_cache(self) -> None:
        """Bulk-load all settings into the in-memory cache."""
        rows = await self.uow.settings.get_all_for_admin(limit=1000)
        for row in rows:
            _CACHE[row.key] = row.value
        # Mirror the cache so synchronous keyboard builders can read it.
        from bot.services import text_store
        text_store.sync_from_cache(_CACHE)

    async def _refresh_key(self, key: str) -> None:
        """Refresh a single key in the cache from the DB (cache-bust on write)."""
        row = await self.uow.settings.get_by_key(key)
        if row:
            _CACHE[key] = row.value
        else:
            _CACHE.pop(key, None)
        from bot.services import text_store
        text_store.sync_from_cache(_CACHE)

    async def ensure_defaults(self) -> None:
        """Insert any missing registry settings (also updates descriptions)."""
        for spec in REGISTRY:
            existing = await self.uow.settings.get_by_key(spec.key)
            if not existing:
                await self.uow.settings.create(
                    key=spec.key,
                    value=spec.default,
                    value_type=spec.value_type,
                    category=spec.category,
                    description=spec.label,
                    is_public=spec.is_public,
                )
            else:
                # Keep the category/label in sync but never overwrite the value.
                if existing.category != spec.category:
                    existing.category = spec.category
                if not existing.description:
                    existing.description = spec.label
        await self.uow.flush()
        await self.load_cache()

    # --- Core get/set ----------------------------------------------------- #
    async def get(self, key: str, default: str | None = None) -> str | None:
        """Get a setting value from cache, falling back to the DB."""
        if key in _CACHE:
            return _CACHE[key]
        row = await self.uow.settings.get_by_key(key)
        if row:
            _CACHE[key] = row.value
            return row.value
        return default

    async def get_int(self, key: str, default: int = 0) -> int:
        value = await self.get(key)
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        value = await self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    async def set(self, key: str, value: str, value_type: str = "string") -> BotSettings:
        spec = spec_for(key)
        vt = spec.value_type if spec else value_type
        setting = await self.uow.settings.set_value(key, value, value_type=vt)
        await self.uow.flush()
        await self._refresh_key(key)  # instant apply
        return setting

    async def set_int(self, key: str, value: int) -> BotSettings:
        return await self.set(key, str(value), value_type="integer")

    async def set_bool(self, key: str, value: bool) -> BotSettings:
        return await self.set(key, "true" if value else "false", value_type="boolean")

    # --- Templates -------------------------------------------------------- #
    async def t(self, key: str, **vars) -> str:
        """Resolve a template setting and interpolate ``{var}`` placeholders."""
        spec = spec_for(key)
        default = spec.default if spec else ""
        template = await self.get(key, default) or ""
        if not template:
            return ""
        try:
            return template.format_map(_SafeFormat(vars))
        except (KeyError, IndexError, ValueError):
            return template

    async def button(self, key: str) -> str:
        """Resolve a button title+emoji label."""
        spec = spec_for(key)
        default = spec.default if spec else key
        return await self.get(key, default) or default

    async def media(self, key: str) -> str:
        """Resolve a media setting (Telegram file_id)."""
        return await self.get(key, "") or ""

    async def feature_enabled(self, feature: Feature) -> bool:
        return await self.get_bool(feature.value, True)

    async def feature_set(self, feature: Feature, enabled: bool) -> BotSettings:
        return await self.set_bool(feature.value, enabled)

    # --- Specific helpers (backward compatible) --------------------------- #
    async def get_payment_info(self) -> dict:
        return {
            "card_number": await self.get(SETTING_CARD_NUMBER, ""),
            "card_holder": await self.get(SETTING_CARD_HOLDER, ""),
            "bank_name": await self.get(SETTING_BANK_NAME, ""),
        }

    async def get_support_text(self) -> str:
        return await self.get(SETTING_SUPPORT_TEXT, "") or ""

    async def get_welcome_message(self) -> str:
        return await self.get(SETTING_WELCOME_MESSAGE, "") or ""

    async def get_admin_telegram_ids(self) -> list[int]:
        """Return admin telegram IDs from settings, merged with OWNER_ID."""
        owner = get_settings().admin_id
        ids = {owner}
        try:
            extra = await self.get(SETTING_ADMIN_IDS, "")
            for part in extra.replace("[", "").replace("]", "").split(","):
                part = part.strip()
                if part.isdigit():
                    ids.add(int(part))
        except Exception:
            logger.debug("could not parse admin_ids setting", exc_info=True)
        return list(ids)

    async def get_all_for_admin(
        self, offset: int = 0, limit: int = 100, category: str | None = None
    ) -> Sequence[BotSettings]:
        return await self.uow.settings.get_all_for_admin(
            offset=offset, limit=limit, category=category
        )


class _SafeFormat(dict):
    """dict wrapper so ``t()`` never crashes on a missing placeholder."""

    def __missing__(self, key):
        return "{" + key + "}"


# In-process cache shared across SettingsService instances.
_CACHE: dict[str, str] = {}