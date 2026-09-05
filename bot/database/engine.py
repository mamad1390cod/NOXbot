"""Database engine and initialization."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from bot.config import get_settings
from bot.models.base import Base


_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            poolclass=NullPool if "sqlite" in settings.database_url else None,
            pool_pre_ping=True,
        )
    return _engine


async def init_db() -> None:
    """Initialize database tables (and validate the ORM first)."""
    from bot.models.compat import ensure_mappers_ready

    # Surfaces a half-declared relationship once, at startup, instead of on
    # every single update - and repairs it when possible.
    ensure_mappers_ready()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database engine."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None