"""Database backup, export and restore utilities."""

import csv
import io
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import Bot

from bot.database.engine import get_engine
from bot.config import get_settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "backups"
EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "exports"


def _ensure_dirs() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


async def create_backup() -> Path:
    """Create a timestamped copy of the SQLite database."""
    _ensure_dirs()
    engine = get_engine()
    url = str(engine.url)
    # Extract sqlite file path from url "sqlite+aiosqlite:///path"
    db_path = url.replace("sqlite+aiosqlite:///", "")
    db_path = db_path.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = str(Path.cwd() / db_path)
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"noxbot_backup_{stamp}.db"
    shutil.copy2(db_path, dest)
    logger.info("Backup created: %s", dest)
    return dest


async def restore_backup(backup_path: Path) -> bool:
    """Restore database from a backup file."""
    _ensure_dirs()
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    engine = get_engine()
    url = str(engine.url)
    db_path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = str(Path.cwd() / db_path)

    # Create a safety copy of the current db
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(db_path, f"{db_path}.pre_restore_{stamp}")

    shutil.copy2(backup_path, db_path)
    logger.info("Database restored from %s", backup_path)
    return True


async def export_tickets_csv(output_path: str | None = None) -> Path:
    """Export all tickets to a CSV file."""
    _ensure_dirs()
    from bot.database.uow import UnitOfWork
    from bot.models.ticket import Ticket

    uow = UnitOfWork()
    tickets = []
    async with uow:
        from sqlalchemy import select
        result = await uow.session.execute(select(Ticket))
        tickets = result.scalars().all()

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(EXPORT_DIR / f"tickets_{stamp}.csv")

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Ticket ID", "User ID", "Category", "Subject", "Message",
            "Status", "Created At", "Closed At",
        ])
        for ticket in tickets:
            writer.writerow([
                ticket.id,
                ticket.user.telegram_id if ticket.user else "",
                ticket.ticket_category.name if ticket.ticket_category else "",
                ticket.subject,
                ticket.message,
                ticket.status.value,
                ticket.created_at.isoformat() if ticket.created_at else "",
                ticket.closed_at.isoformat() if ticket.closed_at else "",
            ])
    logger.info("Tickets exported to %s", output_path)
    return Path(output_path)


async def export_database_json() -> Path:
    """Export key tables to a JSON file for portability."""
    _ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = EXPORT_DIR / f"database_export_{stamp}.json"

    data: dict = {}
    async with get_engine().begin() as conn:
        # Dump all rows from all tables using model metadata
        from bot.models.base import Base
        for table in Base.metadata.sorted_tables:
            rows = (await conn.execute(table.select())).mappings().all()
            data[table.name] = [dict(r) for r in rows]

    # Convert non-serializable values to strings
    def _default(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        try:
            from enum import Enum
            if isinstance(obj, Enum):
                return obj.value
        except Exception:
            pass
        return str(obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_default, indent=2)
    logger.info("Full export to %s", output_path)
    return str(output_path)


def list_backups() -> list[Path]:
    """List available backup files."""
    _ensure_dirs()
    return sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def list_exports() -> list[Path]:
    """List available export files."""
    _ensure_dirs()
    return sorted(EXPORT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)