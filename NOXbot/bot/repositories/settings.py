"""Settings repository."""

from typing import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.settings import BotSettings
from bot.repositories.base import BaseRepository


class SettingsRepository(BaseRepository[BotSettings]):
    """Bot settings repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BotSettings)

    async def get_by_key(self, key: str) -> BotSettings | None:
        """Get setting by key."""
        return await self.get_by(key=key)

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        """Get setting value by key."""
        setting = await self.get_by_key(key)
        return setting.value if setting else default

    async def get_int(self, key: str, default: int = 0) -> int:
        """Get setting as integer."""
        value = await self.get_value(key)
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get setting as boolean."""
        value = await self.get_value(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    async def set_value(self, key: str, value: str, value_type: str = "string", description: str | None = None, category: str = "general") -> BotSettings:
        """Set setting value."""
        setting = await self.get_by_key(key)
        if setting:
            setting.value = value
            setting.value_type = value_type
            if description:
                setting.description = description
            setting.category = category
            await self.session.flush()
            return setting
        return await self.create(
            key=key,
            value=value,
            value_type=value_type,
            description=description,
            category=category,
        )

    async def get_by_category(self, category: str) -> Sequence[BotSettings]:
        """Get all settings by category."""
        stmt = select(BotSettings).where(BotSettings.category == category).order_by(BotSettings.key)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_public_settings(self) -> Sequence[BotSettings]:
        """Get all public settings."""
        stmt = select(BotSettings).where(BotSettings.is_public == True).order_by(BotSettings.category, BotSettings.key)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_for_admin(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        category: str | None = None,
    ) -> Sequence[BotSettings]:
        """Get all settings for admin."""
        stmt = select(BotSettings).order_by(BotSettings.category, BotSettings.key)
        if category:
            stmt = stmt.where(BotSettings.category == category)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()