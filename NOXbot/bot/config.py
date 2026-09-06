"""Configuration module for NOXbot Shop."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Both uppercase (BOT_TOKEN/OWNER_ID) and lowercase (bot_token/owner_id) env
    keys are accepted so the config works with any .env layout.
    """

    _PROJECT_DIR = Path(__file__).resolve().parent.parent
    
    # Search for .env in multiple locations (in order of priority):
    # 1. Current Working Directory
    # 2. Project directory (where this file's parent.parent is)
    # 3. Parent of project directory
    _env_candidates = [
        Path.cwd() / ".env",
        _PROJECT_DIR / ".env",
        _PROJECT_DIR.parent / ".env",
    ]
    _ENV_FILE = next((p for p in _env_candidates if p.exists()), _PROJECT_DIR / ".env")

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # --- Telegram ---
    bot_token: str = Field(..., description="Bot token from @BotFather")
    owner_id: int = Field(
        ..., description="Main admin Telegram ID"
    )

    # Accept both names for the admin id.
    @property
    def admin_id(self) -> int:
        return self.owner_id

    admin_password: str = Field(description="Admin panel password (required in .env)")

    # --- Database ---
    # Absolute path so the DB is always stored in the project folder no matter
    # where the bot is launched from (a relative path would create a fresh DB
    # in the launch directory every time, making data appear to vanish).
    _PROJECT_DIR = Path(__file__).resolve().parent.parent

    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{_PROJECT_DIR / 'noxbot.db'}",
        description="Async SQLAlchemy database URL",
    )

    # --- Runtime ---
    default_language: str = Field(default="fa", description="Default language (fa/en)")
    log_level: str = Field(default="INFO", description="Logging level")

    # --- Cache & Performance ---
    cache_default_ttl: int = Field(default=300, description="Default cache TTL in seconds")
    telegram_max_retries: int = Field(default=3, description="Max Telegram API retries")

    # --- Payment ---
    card_number: str = Field(default="", description="Payment card number")
    card_holder: str = Field(default="", description="Card holder name")
    bank_name: str = Field(default="", description="Bank name")

    # --- Support ---
    support_text: str = Field(
        default="برای پشتیبانی با ادمین تماس بگیرید.",
        description="Support contact text",
    )

    # --- Welcome ---
    welcome_message: str = Field(
        default="به فروشگاه گیمینگ NOXbot خوش آمدید!",
        description="Welcome message for new users",
    )

    # --- Pagination ---
    items_per_page: int = Field(default=10, description="Items per page for pagination")
    admin_items_per_page: int = Field(default=20, description="Admin items per page")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL uses async driver."""
        if v.startswith("sqlite://"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.log_level.upper() != "DEBUG"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance (for dependency injection)."""
    return settings