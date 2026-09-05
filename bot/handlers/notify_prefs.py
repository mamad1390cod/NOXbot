"""User notification-preferences handlers — opt in/out of broadcast categories."""

import logging

from aiogram import F, Router, types
from aiogram.types import Message

from bot.keyboards.common import back_button
from bot.models.user import User
from bot.services.broadcast import BroadcastService

router = Router(name="notify_prefs")
logger = logging.getLogger(__name__)


@router.message(F.text.lower() == "/notify")
async def cmd_notify(message: Message, uow, user: User) -> None:
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📣 اعلان‌های تبلیغاتی", callback_data="notify:toggle:promos")],
        [types.InlineKeyboardButton(text="🛒 اعلان‌های سفارش", callback_data="notify:toggle:orders")],
        [types.InlineKeyboardButton(text="🎮 اعلان‌های کاستوم", callback_data="notify:toggle:tournaments")],
        [back_button("menu:home")],
    ])
    await message.answer("🔔 <b>تنظیمات اعلان‌ها</b>\n\nروی هر گزینه بزنید تا روشن/خاموش شود.", reply_markup=kb)


@router.callback_query(F.data.startswith("notify:toggle:"))
async def cb_toggle(callback, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    category = parts[2]
    bs = BroadcastService(uow)
    prefs = await bs.get_prefs(user)
    was = prefs.get(category, "on")
    new = False if was == "on" else True
    await bs.set_pref(user, category, new)
    await uow.flush()
    state = "✅ روشن" if new else "⚪ خاموش"
    await callback.answer(f"اعلان {category}: {state}", show_alert=True)