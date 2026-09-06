"""Main menu and start handlers (user side)."""

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.common import main_menu_keyboard
from bot.texts import MAIN_MENU, WELCOME

router = Router(name="menu")


async def _send_main_menu(event: Message | CallbackQuery, edit: bool = True) -> None:
    """Send or edit the main menu."""
    settings = get_settings()
    user_id = event.from_user.id if event.from_user else 0
    is_admin = (user_id == settings.admin_id)
    kb = main_menu_keyboard(is_admin=is_admin)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(MAIN_MENU(), reply_markup=kb)
        await event.answer()
    else:
        await event.answer(MAIN_MENU(), reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(WELCOME(), reply_markup=main_menu_keyboard(is_admin=message.from_user.id == get_settings().admin_id))


@router.message(F.text.lower() == "منو" or F.text == "/menu")
async def cmd_menu(message: Message) -> None:
    """Handle /menu command."""
    await _send_main_menu(message, edit=False)


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery) -> None:
    """Handle home button."""
    await _send_main_menu(callback)


@router.callback_query(F.data == "noop" or F.data == "action:noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Handle no-op button clicks."""
    await callback.answer()