"""i18n helpers — dynamic text resolution for handlers.

Handlers receive ``uow`` in their data; wrap it with :class:`TextResolver` to
resolve dynamic, DB-backed texts, buttons, and feature flags.
"""

from bot.services.features import Feature
from bot.services.settings import SettingsService


class TextResolver:
    """Thin wrapper over SettingsService for handler convenience."""

    def __init__(self, uow) -> None:
        self._svc = SettingsService(uow)

    async def t(self, key: str, **vars) -> str:
        """Resolve a text template (may interpolate {vars})."""
        return await self._svc.t(key, **vars)

    async def button(self, key: str) -> str:
        """Resolve a button label."""
        return await self._svc.button(key)

    async def media(self, key: str) -> str:
        """Resolve a media file_id."""
        return await self._svc.media(key)

    async def feature(self, feature: Feature) -> bool:
        """Check a feature flag."""
        return await self._svc.feature_enabled(feature)

    async def text(self, key: str, default: str = "") -> str:
        """Resolve raw text with a fallback."""
        return (await self._svc.get(key, default)) or default