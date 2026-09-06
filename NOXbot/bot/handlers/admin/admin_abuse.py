"""Admin anti-abuse panel — violations, whitelist/blacklist, manual actions."""

import logging
import tempfile

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.abuse import abuse_menu_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.abuse import AntiAbuseService
from bot.services.admin import AdminService
from bot.states import AbusePanelStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_abuse")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:abuse")
async def cb_abuse(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🛡 <b>سیستم ضد سوءاستفاده</b>\n\nانتخاب گزینه:",
        reply_markup=abuse_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "abuse:report")
async def cb_report(callback: CallbackQuery, uow, user: User) -> None:
    abuse = AntiAbuseService(uow)
    rep = await abuse.security_report()
    lines = [
        "📊 <b>گزارش امنیتی</b>\n",
        f"🧾 مجموع رویدادها: {rep['total_events']}",
        f"🚫 کاربران بن‌شده: {rep['blocked_users']}",
        f"⏸ در تعلیق: {rep['suspended']}",
        f"✅ لیست سفید: {rep['whitelisted']}",
        f"⬛ لیست سیاه: {rep['blacklisted']}",
        "",
        "📈 <b>تفکیک نقض‌ها:</b>",
    ]
    for k, v in rep["violations"].items():
        lines.append(f"• {k}: {v}")
    await safe_edit_text(callback, "\n".join(lines), reply_markup=single_button_kb(back_button("admin:abuse")))
    await callback.answer()


@router.callback_query(F.data == "abuse:events")
async def cb_events(callback: CallbackQuery, uow, user: User) -> None:
    abuse = AntiAbuseService(uow)
    events = await abuse.recent_events(limit=15)
    if not events:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:abuse")]])
        await safe_edit_text(callback, "📜 رویدادی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    lines = ["📜 <b>رویدادهای اخیر</b>\n"]
    for e in events:
        who = e.user.username if e.user else "?"
        ts = e.created_at.strftime("%m-%d %H:%M") if e.created_at else ""
        lines.append(f"{ts} | {e.type.value} | {e.severity.value} | @{who}")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:abuse")]])
    await safe_edit_text(callback, "\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "abuse:export")
async def cb_export(callback: CallbackQuery, uow, user: User) -> None:
    """Export security report as CSV and send to admin."""
    abuse = AntiAbuseService(uow)
    rep = await abuse.security_report()
    path = tempfile.mktemp(suffix=".csv")
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["type", "count"])
        for k, v in rep["violations"].items():
            w.writerow([k, v])
        w.writerow([])
        w.writerow(["blocked", rep["blocked_users"]])
        w.writerow(["suspended", rep["suspended"]])
        w.writerow(["blacklisted", rep["blacklisted"]])
    from bot.keyboards.abuse import abuse_menu_keyboard
    await callback.message.answer_document(types.FSInputFile(path), caption="گزارش امنیتی (CSV)")
    await callback.answer("خروجی ارسال شد")


@router.callback_query(F.data == "abuse:clear_counters")
async def cb_clear_counters(callback: CallbackQuery, uow, user: User) -> None:
    abuse = AntiAbuseService(uow)
    # Reset all users' violation counters.
    from sqlalchemy import update
    from bot.models.user import User as _U
    await uow.session.execute(update(_U).values(violation_count=0))
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.USER_EDIT, description="پاک‌کردن شمارنده نقض‌ها")
    await uow.flush()

    await uow.commit()
    await callback.answer("شمارنده‌ها پاک شد")


# --- Whitelist / blacklist ------------------------------------------------- #
@router.callback_query(F.data == "abuse:bl_list")
async def cb_bl_list(callback: CallbackQuery, uow, user: User) -> None:
    from sqlalchemy import select
    from bot.models.user import User as _U
    users = (await uow.session.execute(select(_U).where(_U.blacklisted == True))).scalars().all()
    if not users:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:abuse")]])
        await safe_edit_text(callback, "⬛ کاربری در لیست سیاه نیست.", reply_markup=kb)
        await callback.answer()
        return
    lines = ["⬛ <b>لیست سیاه</b>\n"]
    for u in users:
        lines.append(f"• @{u.username or u.telegram_id} — {u.blacklist_reason or ''}")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:abuse")]])
    await safe_edit_text(callback, "\n".join(lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "abuse:bl_add")
async def cb_bl_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AbusePanelStates.waiting_tg_id)
    await callback.message.answer("⬛ آیدی عددی کاربر را برای افزودن به لیست سیاه ارسال کنید:")
    await callback.answer()


@router.message(AbusePanelStates.waiting_tg_id)
async def do_bl_add(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ آیدی عددی معتبر ارسال کنید:")
        return
    tg_id = int(message.text.strip())
    abuse = AntiAbuseService(uow)
    target = await abuse.blacklist_user(tg_id)
    if not target:
        await message.answer("❌ کاربر یافت نشد.")
        await state.clear()
        return
    await state.clear()
    await message.answer(f"✅ کاربر @{target.username or target.telegram_id} به لیست سیاه اضافه شد.",
                         reply_markup=single_button_kb(back_button("admin:abuse")))


# --- Placeholders for other actions are gated to keep scope tight ---------- #
# (wl_list / manual mute/ban wired in the same file below)
@router.callback_query(F.data == "abuse:wl_list")
async def cb_wl_list(callback: CallbackQuery, uow, user: User) -> None:
    from sqlalchemy import select
    from bot.models.user import User as _U
    users = (await uow.session.execute(select(_U).where(_U.whitelisted == True))).scalars().all()
    if not users:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:abuse")]])
        await safe_edit_text(callback, "✅ کاربری در لیست سفید نیست.", reply_markup=kb)
        await callback.answer()
        return
    lines = ["✅ <b>لیست سفید</b>\n"]
    for u in users:
        lines.append(f"• @{u.username or u.telegram_id}")
    keyboard = []
    for u in users[:10]:
        keyboard.append([types.InlineKeyboardButton(
            text=f"حذف @{u.username or u.telegram_id}",
            callback_data=f"abuse:wl_del:{u.telegram_id}",
        )])
    keyboard.append([back_button("admin:abuse")])
    await safe_edit_text(callback, "\n".join(lines), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data.startswith("abuse:wl_del:"))
async def cb_wl_del(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("آیدی یافت نشد", show_alert=True)
        return
    tg_id = int(parts[2])
    abuse = AntiAbuseService(uow)
    await abuse.unblacklist_user(tg_id)
    # also clear whitelist flag fully - use parameterized query
    from sqlalchemy import update, text
    from bot.models.user import User as _U
    await uow.session.execute(
        update(_U).where(_U.telegram_id == tg_id).values(
            whitelisted=False, blacklisted=False
        )
    )
    await uow.flush()

    await uow.commit()
    await callback.answer("حذف شد")
    await cb_wl_list(callback, uow, user)