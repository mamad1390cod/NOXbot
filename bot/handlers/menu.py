"""Main menu and start handlers (user side)."""

import logging

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.common import main_menu_keyboard
from bot.texts import MAIN_MENU, WELCOME
from bot.utils.editing import safe_edit_text

router = Router(name="menu")
logger = logging.getLogger(__name__)


async def _is_admin(user_id: int, uow=None, user=None) -> bool:
    """True for the owner and for any user with an ACTIVE admin profile.

    The main menu used to compare against ``OWNER_ID`` only, so admins added
    through the RBAC panel never saw the 👑 مدیریت button.
    """
    if user_id == get_settings().admin_id:
        return True
    try:
        from bot.services.rbac import RbacService

        if uow is not None and user is not None:
            return await RbacService(uow).is_admin(user)
        from bot.database.uow import UnitOfWork

        async with UnitOfWork() as fresh:
            rbac = RbacService(fresh)
            db_user = await fresh.users.get_by_telegram_id(user_id)
            return bool(db_user) and await rbac.is_admin(db_user)
    except Exception as e:  # never block the menu because of an RBAC hiccup
        logger.warning("admin check failed for %s: %s", user_id, e)
        return False


async def _send_main_menu(event: Message | CallbackQuery, uow=None, user=None) -> None:
    """Send or edit the main menu."""
    user_id = event.from_user.id if event.from_user else 0
    kb = main_menu_keyboard(is_admin=await _is_admin(user_id, uow, user))

    if isinstance(event, CallbackQuery):
        # safe_edit_text falls back to caption-edit / new message, so the home
        # button also works when the current message is a photo or video.
        await safe_edit_text(event, MAIN_MENU(), reply_markup=kb)
        await event.answer()
    else:
        await event.answer(MAIN_MENU(), reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, uow=None, user=None) -> None:
    """Handle /start command."""
    kb = main_menu_keyboard(is_admin=await _is_admin(message.from_user.id, uow, user))
    await message.answer(WELCOME(), reply_markup=kb)


# NOTE: `F.text == "منو" or F.text == "/menu"` is a Python `or` on two magic
# filters — it evaluates to the *first* object, so "/menu" was never handled.
@router.message(Command("menu"))
async def cmd_menu(message: Message, uow=None, user=None) -> None:
    """Handle the /menu command."""
    await _send_main_menu(message, uow, user)


@router.message(F.text.in_({"منو", "منو اصلی", "🏠 منو"}))
async def txt_menu(message: Message, uow=None, user=None) -> None:
    """Handle the plain-text menu shortcut."""
    await _send_main_menu(message, uow, user)


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, uow=None, user=None) -> None:
    """Handle home button."""
    await _send_main_menu(callback, uow, user)


# Same `or` bug as above: "action:noop" (used by the pagination counter) never
# reached a handler and left the click spinning.
@router.callback_query(F.data.in_({"noop", "action:noop"}))
async def cb_noop(callback: CallbackQuery) -> None:
    """Handle no-op button clicks."""
    await callback.answer()


# Single global cancel handler (account.py used to define a second one that
# cleared the state but left the user on a screen without any buttons).
@router.callback_query(F.data == "action:cancel")
async def cb_cancel(callback: CallbackQuery, state=None, uow=None, user=None) -> None:
    """Global cancel: drop any FSM state and return to the main menu."""
    if state is not None:
        await state.clear()
    await callback.answer("لغو شد")
    await _send_main_menu(callback, uow, user)
