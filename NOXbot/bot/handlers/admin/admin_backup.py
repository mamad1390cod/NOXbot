"""Admin database backup and restore handlers."""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.states import AdminBackupStates

router = Router(name="admin_backup")
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Get database file path."""
    # Default SQLite database path
    return Path("noxbot.db")


@router.callback_query(F.data == "admin:backup")
async def cb_admin_backup(callback: CallbackQuery) -> None:
    """Show backup menu."""
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💾 دانلود بکاپ", callback_data="abackup:download")],
        [types.InlineKeyboardButton(text="📤 آپلود بکاپ", callback_data="abackup:upload")],
        [back_button("admin:panel")],
    ])
    await callback.message.edit_text(
        "💾 <b>مدیریت بکاپ دیتابیس</b>\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "abackup:download")
async def cb_backup_download(callback: CallbackQuery, user: User) -> None:
    """Download database backup."""
    db_path = get_db_path()
    
    if not db_path.exists():
        await callback.answer("❌ فایل دیتابیس یافت نشد", show_alert=True)
        return
    
    try:
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"noxbot_backup_{timestamp}.db"
        backup_path = Path("backups") / backup_filename
        
        # Create backups directory if not exists
        backup_path.parent.mkdir(exist_ok=True)
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        # Send file to user
        file = FSInputFile(backup_path, filename=backup_filename)
        await callback.message.answer_document(
            file,
            caption=f"💾 <b>بکاپ دیتابیس</b>\n\n"
                    f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📦 حجم: {backup_path.stat().st_size / 1024:.2f} KB\n\n"
                    f"⚠️ این فایل را در جای امن نگهداری کنید."
        )
        
        # Clean up backup file
        backup_path.unlink()
        
        await callback.answer("✅ بکاپ با موفقیت ارسال شد", show_alert=True)
        logger.info(f"Admin {user.telegram_id} downloaded database backup")
        
    except Exception as e:
        logger.exception(f"Failed to create backup: {e}")
        await callback.answer(f"❌ خطا در ایجاد بکاپ: {e}", show_alert=True)


@router.callback_query(F.data == "abackup:upload")
async def cb_backup_upload(callback: CallbackQuery, state: FSMContext) -> None:
    """Start backup upload process."""
    await state.set_state(AdminBackupStates.waiting_backup_file)
    await callback.message.edit_text(
        "📤 <b>آپلود بکاپ</b>\n\n"
        "فایل بکاپ دیتابیس (.db) را ارسال کنید:\n\n"
        "⚠️ <b>هشدار:</b> این عملیات دیتابیس فعلی را با فایل آپلود شده جایگزین می‌کند.\n"
        "تمام داده‌های فعلی از بین خواهد رفت!",
        reply_markup=single_button_kb(back_button("admin:backup"))
    )
    await callback.answer()


@router.message(AdminBackupStates.waiting_backup_file, F.document)
async def collect_backup_file(message: Message, state: FSMContext, user: User) -> None:
    """Receive and restore backup file."""
    document = message.document
    
    # Validate file extension
    if not document.file_name.endswith('.db'):
        await message.answer(
            "❌ فایل نامعتبر است. فقط فایل‌های .db قابل قبول هستند.",
            reply_markup=single_button_kb(back_button("admin:backup"))
        )
        await state.clear()
        return
    
    try:
        # Download file
        file = await message.bot.get_file(document.file_id)
        temp_path = Path("temp_backup.db")
        await message.bot.download_file(file.file_path, temp_path)
        
        # Validate downloaded file
        if temp_path.stat().st_size == 0:
            temp_path.unlink()
            await message.answer(
                "❌ فایل خالی است.",
                reply_markup=single_button_kb(back_button("admin:backup"))
            )
            await state.clear()
            return
        
        # Backup current database before restore
        db_path = get_db_path()
        if db_path.exists():
            backup_before_restore = Path(f"backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            shutil.copy2(db_path, backup_before_restore)
            logger.info(f"Created backup before restore: {backup_before_restore}")
        
        # Restore database
        shutil.move(temp_path, db_path)
        
        await state.clear()
        await message.answer(
            "✅ <b>بکاپ با موفقیت بازیابی شد</b>\n\n"
            "⚠️ برای اعمال تغییرات، بات را ریستارت کنید.\n\n"
            "💡 یک بکاپ از دیتابیس قبلی با نام "
            f"<code>backup_before_restore_*.db</code> ذخیره شد.",
            reply_markup=single_button_kb(back_button("admin:panel"))
        )
        
        logger.warning(f"Admin {user.telegram_id} restored database from backup")
        
    except Exception as e:
        logger.exception(f"Failed to restore backup: {e}")
        await state.clear()
        await message.answer(
            f"❌ خطا در بازیابی بکاپ: {e}",
            reply_markup=single_button_kb(back_button("admin:backup"))
        )


@router.message(AdminBackupStates.waiting_backup_file)
async def invalid_backup_file(message: Message) -> None:
    """Handle invalid file type."""
    await message.answer(
        "❌ لطفاً یک فایل .db ارسال کنید.",
        reply_markup=single_button_kb(back_button("admin:backup"))
    )
