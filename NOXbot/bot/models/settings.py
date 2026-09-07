"""Bot settings model."""

from sqlalchemy import (
    Boolean,
    BigInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin, UUIDMixin


class BotSettings(Base, UUIDMixin, TimestampMixin):
    """Global bot settings model."""

    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    value_type: Mapped[str] = mapped_column(
        String(20),
        default="string",
        nullable=False,
    )  # string, integer, boolean, json
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # Can be shown to users
    category: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
    )  # general, payment, support, shop, custom

    def __repr__(self) -> str:
        return f"<BotSettings(key={self.key}, value={self.value[:50]})>"