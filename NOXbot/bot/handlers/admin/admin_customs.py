"""Admin custom tournament management handlers."""

import logging

from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import custom_admin_detail_keyboard, custom_admin_list_keyboard, admin_customs_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.custom import CustomType, WinnerType
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.custom import CustomService
from bot.services.notification import NotificationService
from bot.states import CustomStates
from bot.texts import CONGRATULATIONS, TOURNAMENT_ENDED
from bot.utils.editing import safe_edit_text
from bot.utils.format import format_price

router = Router(name="admin_customs")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:customs")
async def cb_admin_customs(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "🎮 <b>مدیریت کاستوم‌ها</b>", reply_markup=admin_customs_keyboard())
    await callback.answer()


# --- Create custom flow ---
@router.callback_query(F.data == "acustom:add")
async def cb_custom_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    # Ask free/paid first
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🆓 رایگان", callback_data="acustom:add_type:free")],
        [types.InlineKeyboardButton(text="💰 پولی", callback_data="acustom:add_type:paid")],
        [back_button("admin:customs")],
    ])
    await safe_edit_text(callback, "🎮 نوع کاستوم را انتخاب کنید:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:add_type:"))
async def cb_custom_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("نوع کاستوم نامعتبر", show_alert=True)
        return
    ctype = parts[2]
    await state.update_data(custom_type=CustomType.FREE if ctype == "free" else CustomType.PAID)
    await state.set_state(CustomStates.waiting_title)
    await callback.message.answer("📝 عنوان کاستوم را ارسال کنید:")
    await callback.answer()


@router.message(CustomStates.waiting_title)
async def collect_custom_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ عنوان خالی است:")
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(CustomStates.waiting_description)
    await message.answer("📝 توضیحات کاستوم را ارسال کنید (یا /skip):")


@router.message(CustomStates.waiting_description)
async def collect_custom_desc(message: Message, state: FSMContext) -> None:
    desc = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    await state.update_data(description=desc)
    await state.set_state(CustomStates.waiting_rules)
    await message.answer("📜 قوانین کاستوم را ارسال کنید (یا /skip):")


@router.message(CustomStates.waiting_rules)
async def collect_custom_rules(message: Message, state: FSMContext) -> None:
    rules = message.text.strip() if message.text and not message.text.startswith("/skip") else ""
    await state.update_data(rules=rules)
    await state.set_state(CustomStates.waiting_date)
    await message.answer("📅 تاریخ برگزاری را ارسال کنید (مثال: 1404-05-15 یا 2026-08-15) — یا /skip:")


@router.message(CustomStates.waiting_date)
async def collect_custom_date(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    event_date = None
    if not raw.startswith("/skip"):
        try:
            event_date = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            await message.answer("⚠️ فرمت تاریخ صحیح نیست. مثال: 2026-08-15 — یا /skip:")
            return
    await state.update_data(event_date=event_date)
    await state.set_state(CustomStates.waiting_time)
    await message.answer("🕒 زمان برگزاری را ارسال کنید (مثال: 20:00) — یا /skip:")


@router.message(CustomStates.waiting_time)
async def collect_custom_time(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    event_time = None if raw.startswith("/skip") else raw
    await state.update_data(event_time=event_time)
    await state.set_state(CustomStates.waiting_prize)
    await message.answer("🏆 جایزه کاستوم را ارسال کنید (یا /skip):")


@router.message(CustomStates.waiting_prize)
async def collect_custom_prize(message: Message, state: FSMContext) -> None:
    prize = message.text.strip() if message.text and not message.text.startswith("/skip") else None
    await state.update_data(prize=prize)
    await state.set_state(CustomStates.waiting_entry_fee)
    await message.answer("💰 هزینه ورود (تومان) را ارسال کنید — برای رایگان 0:")


@router.message(CustomStates.waiting_entry_fee)
async def collect_custom_fee(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        fee = int(message.text.strip().replace(",", ""))
        if fee < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    await state.update_data(entry_fee=fee)
    await state.set_state(CustomStates.waiting_capacity)
    await message.answer("🎯 حداکثر ظرفیت بازیکنان را ارسال کنید (عدد):")


@router.message(CustomStates.waiting_capacity)
async def collect_custom_capacity(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text:
        await message.answer("⚠️ عدد معتبر وارد کنید:")
        return
    try:
        cap = int(message.text.strip())
        if cap <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ عدد صحیح بزرگتر از صفر وارد کنید:")
        return
    await state.update_data(max_capacity=cap)
    await state.set_state(CustomStates.waiting_category)
    from bot.keyboards.selectors import category_picker_keyboard
    cs = CustomService(uow)
    cats = await cs.get_active_categories()
    await message.answer(
        "📂 <b>انتخاب دسته کاستوم</b>\n\nروی یکی از دسته‌های موجود بزنید (یا «بدون دسته»):",
        reply_markup=category_picker_keyboard(
            cats,
            callback_prefix="pickcat_custom",
            back_to="admin:customs",
        ),
    )


@router.callback_query(F.data.startswith("pickcat_custom:"))
async def collect_custom_category(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    raw = parts[1]
    category_id = None if raw == "none" else raw
    data = await state.get_data()

    cs = CustomService(uow)

    custom = await cs.create_custom(
        title=data.get("title"),
        custom_category_id=category_id,
        custom_type=data.get("custom_type", CustomType.FREE),
        description=data.get("description") or "",
        rules=data.get("rules") or "",
        entry_fee=data.get("entry_fee", 0),
        prize=data.get("prize"),
        event_date=data.get("event_date"),
        event_time=data.get("event_time"),
        max_capacity=data.get("max_capacity"),
        is_visible=True,
    )
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.CUSTOM_CREATE, target_id=custom.id, description=f"ایجاد کاستوم {custom.title}")
    await uow.flush()

    await uow.commit()
    await state.clear()

    text = (
        "✅ <b>کاستوم ایجاد شد</b>\n\n"
        f"🎮 عنوان: {custom.title}\n"
        f"💰 هزینه: {'رایگان' if custom.type.value == 'free' else format_price(custom.entry_fee)}\n"
        f"🎯 ظرفیت: {custom.max_capacity}\n\n"
        "برای فعال‌سازی ثبت‌نام، ابتدا جایزه را تعیین کنید و سپس از منوی کاستوم گزینه «باز کردن ثبت‌نام» را بزنید."
    )
    await safe_edit_text(callback, text, reply_markup=custom_admin_detail_keyboard(custom.id, custom))
    await callback.answer("کاستوم ایجاد شد")


# --- List customs ---
@router.callback_query(F.data == "acustom:list")
async def cb_custom_list(callback: CallbackQuery, uow, user: User) -> None:
    cs = CustomService(uow)
    customs = await cs.get_all_for_admin(limit=50)
    if not customs:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:customs")]])
        await safe_edit_text(callback, "🎮 کاستومی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "🎮 <b>لیست کاستوم‌ها</b>", reply_markup=custom_admin_list_keyboard(customs))
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:view:"))
async def cb_custom_view(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    cs = CustomService(uow)
    custom = await cs.get_custom(custom_id)
    if not custom:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    text = _custom_summary(custom)
    await safe_edit_text(callback, text, reply_markup=custom_admin_detail_keyboard(custom_id, custom))
    await callback.answer()


def _custom_summary(custom) -> str:
    fee = "رایگان" if custom.type.value == "free" else f"{format_price(custom.entry_fee)} تومان"
    cap = f"{custom.current_players}/{custom.max_capacity}" if custom.max_capacity else str(custom.current_players)
    reg = "🟢 باز" if custom.registration_open else "🔴 بسته"
    status_map = {
        "draft": "پیش‌نویس",
        "ready": "آماده",
        "registration_open": "ثبت‌نام باز",
        "registration_closed": "ثبت‌نام بسته",
        "started": "شروع شده",
        "in_progress": "در جریان",
        "completed": "تکمیل شده",
        "cancelled": "لغو شده"
    }
    status = status_map.get(custom.status.value, custom.status.value)
    date = custom.event_date.strftime("%Y-%m-%d") if custom.event_date else "—"
    
    # Prize status
    prize_status = "✅ تعیین شده" if custom.prize_set else "❌ تعیین نشده"
    if custom.prize_set and custom.prize_file_type:
        if custom.prize_file_type == "text":
            prize_status += " (متن)"
        else:
            prize_status += f" ({custom.prize_file_type})"
    
    # Start message status
    start_msg_status = "✅ تنظیم شده" if custom.start_message else "❌ تنظیم نشده"
    
    return (
        f"🎮 <b>{custom.title}</b>\n\n"
        f"📝 توضیحات: {custom.description or '—'}\n"
        f"📜 قوانین: {custom.rules or '—'}\n"
        f"📅 تاریخ: {date} {custom.event_time or ''}\n"
        f"🎁 جایزه: {prize_status}\n"
        f"📝 متن شروع: {start_msg_status}\n"
        f"💰 هزینه: {fee}\n"
        f"👥 بازیکنان: {cap}\n"
        f"📊 وضعیت: {status}\n"
        f"📥 ثبت‌نام: {reg}\n"
    )


# --- Toggle registration ---
@router.callback_query(F.data.startswith("acustom:open:"))
async def cb_custom_open_reg(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    cs = CustomService(uow)
    try:
        custom = await cs.set_registration_status(custom_id, True)
        await uow.flush()

        await uow.commit()
        if custom:
            await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))
        await callback.answer("ثبت‌نام باز شد")
    except ValueError as e:
        await callback.answer(f"❌ خطا: {e}", show_alert=True)


@router.callback_query(F.data.startswith("acustom:close:"))
async def cb_custom_close_reg(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    cs = CustomService(uow)
    custom = await cs.set_registration_status(custom_id, False)
    await uow.flush()

    await uow.commit()
    if custom:
        await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))
    await callback.answer("ثبت‌نام بسته شد")


# --- Players list ---
@router.callback_query(F.data.startswith("acustom:players:"))
async def cb_custom_players(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    cs = CustomService(uow)
    registrations = await cs.get_registrations(custom_id)
    if not registrations:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:customs")]])
        await safe_edit_text(callback, "👥 بازیکنی ثبت‌نام نکرده است.", reply_markup=kb)
        await callback.answer()
        return
    lines = []
    for i, reg in enumerate(registrations, 1):
        ruser = reg.user
        lines.append(
            f"{i}. {reg.codm_username} — @{ruser.username or '-'} — {reg.status}"
        )
    text = "👥 <b>بازیکنان کاستوم</b>\n\n" + "\n".join(lines)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:customs")]])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


# --- Delete ---
@router.callback_query(F.data.startswith("acustom:del:"))
async def cb_custom_delete(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    cs = CustomService(uow)
    await cs.delete_custom(custom_id)
    await uow.flush()

    await uow.commit()
    await callback.answer("حذف شد")
    await safe_edit_text(callback, "✅ کاستوم حذف شد.", reply_markup=single_button_kb(back_button("admin:customs")))


# --- Cancel ---
@router.callback_query(F.data.startswith("acustom:cancel:"))
async def cb_custom_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    await state.set_data({"cancel_custom_id": custom_id})
    await state.set_state(CustomStates.waiting_cancel_reason)
    await callback.message.answer("⚠️ دلیل لغو کاستوم را بنویسید:")
    await callback.answer()


@router.message(CustomStates.waiting_cancel_reason)
async def do_custom_cancel(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    custom_id = data.get("cancel_custom_id")
    reason = message.text.strip() if message.text else ""
    cs = CustomService(uow)
    custom = await cs.cancel_custom(custom_id, reason)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.CUSTOM_CANCEL, target_id=custom_id, description=reason)
    await uow.flush()

    await uow.commit()

    # Notify participants
    if custom:
        regs = await cs.get_registrations(custom_id)
        notifier = NotificationService(message.bot, uow)
        for reg in regs:
            if reg.user:
                await notifier.notify_user(
                    reg.user.telegram_id,
                    f"❌ کاستوم «{custom.title}» لغو شد.\n\nدلیل: {reason}",
                )
    await state.clear()
    await message.answer("✅ کاستوم لغو شد.")


# --- Notify participants ---
@router.callback_query(F.data.startswith("acustom:notify:"))
async def cb_custom_notify(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    await state.set_data({"notify_custom_id": custom_id})
    await state.set_state(CustomStates.waiting_notify_message)
    await callback.message.answer("📣 پیام اطلاع‌رسانی به شرکت‌کنندگان را بنویسید:")
    await callback.answer()


@router.message(CustomStates.waiting_notify_message)
async def do_custom_notify(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    custom_id = data.get("notify_custom_id")
    text = message.text.strip() if message.text else ""
    cs = CustomService(uow)
    registrations = await cs.broadcast_to_participants(custom_id)
    notifier = NotificationService(message.bot, uow)
    count = 0
    for reg in registrations:
        if reg.user:
            await notifier.notify_user(reg.user.telegram_id, text)
            count += 1
    await state.clear()
    await message.answer(f"✅ پیام برای <b>{count}</b> شرکت‌کننده ارسال شد.")


# --- Winner selection ---
@router.callback_query(F.data.startswith("acustom:winner:"))
async def cb_custom_winner(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👤 یک بازیکن", callback_data=f"acustom:winner_type:{custom_id}:player")],
        [types.InlineKeyboardButton(text="👥 یک تیم", callback_data=f"acustom:winner_type:{custom_id}:team")],
        [back_button("admin:customs")],
    ])
    await safe_edit_text(callback, "🏆 نوع برنده را انتخاب کنید:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:winner_type:"))
async def cb_custom_winner_type(callback: CallbackQuery, uow, user: User, state: FSMContext) -> None:
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("داده‌های نامعتبر", show_alert=True)
        return
    custom_id = parts[2]
    wtype = parts[3]

    cs = CustomService(uow)
    registrations = await cs.get_registrations(custom_id)

    if wtype == "player":
        # Store custom_id in state to avoid callback_data exceeding 64 bytes
        await state.update_data(pick_custom_id=custom_id)
        # Show list of players to pick from
        keyboard = []
        for reg in registrations:
            label = f"{reg.codm_username}"
            keyboard.append([
                types.InlineKeyboardButton(text=label, callback_data=f"cpk:{reg.id}")
            ])
        keyboard.append([back_button("admin:customs")])
        await safe_edit_text(callback, "🏆 انتخاب برنده (بازیکن):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        # Team: ask for team name
        await state.set_data({"winner_custom_id": custom_id, "winner_type": WinnerType.TEAM})
        await state.set_state(CustomStates.waiting_winner_team_name)
        await callback.message.answer("👥 نام تیم برنده را ارسال کنید:")
    await callback.answer()


@router.message(CustomStates.waiting_winner_team_name)
async def do_winner_team(message: Message, state: FSMContext, uow, user: User) -> None:
    data = await state.get_data()
    custom_id = data.get("winner_custom_id")
    team_name = message.text.strip() if message.text else ""
    cs = CustomService(uow)
    custom = await cs.set_winner(custom_id, WinnerType.TEAM, winner_team_name=team_name)
    await uow.flush()

    await uow.commit()
    await _announce_winner(message.bot, uow, custom_id, user, custom)
    await state.clear()
    await message.answer("✅ برنده ثبت شد و اعلام شد.")


@router.callback_query(F.data.startswith("cpk:"))
async def cb_custom_pick_winner(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("بازیکن یافت نشد", show_alert=True)
        return
    reg_id = parts[1]
    data = await state.get_data()
    custom_id = data.get("pick_custom_id")
    if not custom_id:
        await callback.answer("خطا: اطلاعات جلسه یافت نشد", show_alert=True)
        return
    cs = CustomService(uow)
    reg = await cs.get_registration(reg_id)
    if not reg:
        await callback.answer("بازیکن یافت نشد", show_alert=True)
        return
    custom = await cs.set_winner(custom_id, WinnerType.PLAYER, winner_user_id=reg.user_id)
    await uow.flush()

    await uow.commit()
    await _announce_winner(callback.bot, uow, custom_id, user, custom)
    await state.clear()
    await callback.answer("برنده ثبت شد")
    await safe_edit_text(callback, "✅ برنده ثبت شد و اعلام شد.")


async def _announce_winner(bot, uow, custom_id: str, admin: User, custom) -> None:
    """Notify all participants and the winner."""
    cs = CustomService(uow)
    # Reload custom with winner relationship
    custom = await cs.get_custom(custom_id)
    if not custom:
        return
    registrations = await cs.get_registrations(custom_id)
    notifier = NotificationService(bot, uow)

    # Tournament ended for all participants
    ended_msg = (
        f"🏁 <b>مسابقه پایان یافت.</b>\n\n"
        f"برنده مشخص شد: "
    )
    if custom.winner_team_name:
        ended_msg += f"<b>{custom.winner_team_name}</b>"
    elif custom.winner:
        ended_msg += f"<b>{custom.winner.first_name or 'بازیکن'}</b>"
    else:
        ended_msg += "—"

    winner_tg_id = custom.winner.telegram_id if custom.winner else None
    for reg in registrations:
        if reg.user:
            await notifier.notify_user(reg.user.telegram_id, ended_msg)
            # If this user is the winner, send congratulations
            if winner_tg_id and reg.user.telegram_id == winner_tg_id:
                await notifier.notify_user(reg.user.telegram_id, CONGRATULATIONS())

    api = AdminService(uow)
    await api.log_action(admin, LogAction.CUSTOM_WINNER, target_id=custom_id, description="انتخاب برنده")


# ============================================================================
# Prize Management Handlers
# ============================================================================

@router.callback_query(F.data.startswith("acustom:view_prize:"))
async def cb_custom_view_prize(callback: CallbackQuery, uow) -> None:
    """View prize content."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    cs = CustomService(uow)
    custom = await cs.get_custom(custom_id)
    
    if not custom or not custom.prize_set:
        await callback.answer("جایزه‌ای تنظیم نشده است", show_alert=True)
        return
    
    # Send prize based on type
    if custom.prize_file_type == "text" and custom.prize:
        await callback.message.answer(f"🎁 <b>جایزه کاستوم:</b>\n\n{custom.prize}")
    elif custom.prize_file_id:
        # Send media with caption
        caption = custom.prize_caption or "🎁 جایزه کاستوم"
        try:
            if custom.prize_file_type == "photo":
                await callback.message.answer_photo(custom.prize_file_id, caption=caption)
            elif custom.prize_file_type == "video":
                await callback.message.answer_video(custom.prize_file_id, caption=caption)
            elif custom.prize_file_type == "document":
                await callback.message.answer_document(custom.prize_file_id, caption=caption)
            elif custom.prize_file_type == "audio":
                await callback.message.answer_audio(custom.prize_file_id, caption=caption)
            elif custom.prize_file_type == "voice":
                await callback.message.answer_voice(custom.prize_file_id, caption=caption)
            elif custom.prize_file_type == "animation":
                await callback.message.answer_animation(custom.prize_file_id, caption=caption)
            else:
                await callback.message.answer_document(custom.prize_file_id, caption=caption)
        except Exception as e:
            logger.error(f"Failed to send prize media: {e}")
            await callback.message.answer(f"🎁 جایزه: {custom.prize_file_type} (ارسال با خطا مواجه شد)")
    
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:view_start_msg:"))
async def cb_custom_view_start_message(callback: CallbackQuery, uow) -> None:
    """View start message."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    cs = CustomService(uow)
    custom = await cs.get_custom(custom_id)
    
    if not custom or not custom.start_message:
        await callback.answer("متن شروع تنظیم نشده است", show_alert=True)
        return
    
    await callback.message.answer(
        f"📝 <b>متن شروع کاستوم:</b>\n\n{custom.start_message}"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:set_prize:"))
async def cb_custom_set_prize(callback: CallbackQuery, state: FSMContext) -> None:
    """Start prize setting flow."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    await state.update_data(prize_custom_id=custom_id)
    await state.set_state(CustomStates.waiting_prize_content)
    await callback.message.answer(
        "🎁 <b>تعیین جایزه کاستوم</b>\n\n"
        "لطفاً جایزه را ارسال کنید. می‌توانید هر نوع محتوایی بفرستید:\n"
        "• 📝 متن\n"
        "• 🖼 عکس\n"
        "• 🎥 ویدیو\n"
        "• 🎵 فایل صوتی\n"
        "• 🎙 Voice\n"
        "• 📄 فایل (ZIP, RAR, PDF, etc.)\n\n"
        "یا برای انصراف /cancel را بزنید."
    )
    await callback.answer()


@router.message(CustomStates.waiting_prize_content)
async def collect_prize_content(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect prize content (text or media)."""
    data = await state.get_data()
    custom_id = data.get("prize_custom_id")
    
    if message.text and message.text == "/cancel":
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
        return
    
    cs = CustomService(uow)
    
    prize_text = None
    prize_file_id = None
    prize_file_type = None
    prize_caption = None
    
    # Determine message type and extract data
    if message.text:
        prize_text = message.text.strip()
        prize_file_type = "text"
    elif message.photo:
        prize_file_id = message.photo[-1].file_id
        prize_file_type = "photo"
        prize_caption = message.caption
    elif message.video:
        prize_file_id = message.video.file_id
        prize_file_type = "video"
        prize_caption = message.caption
    elif message.document:
        prize_file_id = message.document.file_id
        prize_file_type = "document"
        prize_caption = message.caption
    elif message.audio:
        prize_file_id = message.audio.file_id
        prize_file_type = "audio"
        prize_caption = message.caption
    elif message.voice:
        prize_file_id = message.voice.file_id
        prize_file_type = "voice"
        prize_caption = message.caption
    elif message.animation:
        prize_file_id = message.animation.file_id
        prize_file_type = "animation"
        prize_caption = message.caption
    else:
        await message.answer("⚠️ نوع محتوا پشتیبانی نمی‌شود. لطفاً متن، عکس، ویدیو یا فایل ارسال کنید.")
        return
    
    # Save prize
    try:
        custom = await cs.set_prize(
            custom_id,
            prize_text=prize_text,
            prize_file_id=prize_file_id,
            prize_file_type=prize_file_type,
            prize_caption=prize_caption,
        )
        await uow.flush()

        await uow.commit()
        
        # Log action
        api = AdminService(uow)
        await api.log_action(user, LogAction.CUSTOM_UPDATE, target_id=custom_id, description=f"تعیین جایزه ({prize_file_type})")
        await uow.flush()

        await uow.commit()
        
        await state.clear()
        
        # Show success message
        success_text = "✅ <b>جایزه با موفقیت تعیین شد</b>\n\n"
        if prize_file_type == "text":
            success_text += f"📝 نوع: متن\n📄 محتوا: {prize_text[:100]}{'...' if len(prize_text) > 100 else ''}"
        else:
            success_text += f"📦 نوع: {prize_file_type}"
            if prize_caption:
                success_text += f"\n📝 کپشن: {prize_caption[:100]}{'...' if len(prize_caption) > 100 else ''}"
        
        await message.answer(success_text, reply_markup=custom_admin_detail_keyboard(custom_id, custom))
        
    except ValueError as e:
        await state.clear()
        await message.answer(f"❌ خطا: {e}")


@router.callback_query(F.data.startswith("acustom:edit_prize:"))
async def cb_custom_edit_prize(callback: CallbackQuery, state: FSMContext) -> None:
    """Edit existing prize."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    # Same flow as set_prize
    await state.update_data(prize_custom_id=custom_id)
    await state.set_state(CustomStates.waiting_prize_content)
    await callback.message.answer(
        "✏️ <b>ویرایش جایزه کاستوم</b>\n\n"
        "لطفاً جایزه جدید را ارسال کنید. جایزه قبلی جایگزین خواهد شد.\n\n"
        "یا برای انصراف /cancel را بزنید."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acustom:clear_prize:"))
async def cb_custom_clear_prize(callback: CallbackQuery, uow, user: User) -> None:
    """Clear prize from custom."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    cs = CustomService(uow)
    try:
        await cs.clear_prize(custom_id)
        await uow.flush()

        await uow.commit()
        
        # Log action
        api = AdminService(uow)
        await api.log_action(user, LogAction.CUSTOM_UPDATE, target_id=custom_id, description="حذف جایزه")
        await uow.flush()

        await uow.commit()
        
        await callback.answer("✅ جایزه حذف شد", show_alert=True)
        
        # Refresh view
        custom = await cs.get_custom(custom_id)
        if custom:
            await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))
    except ValueError as e:
        await callback.answer(f"❌ خطا: {e}", show_alert=True)


# ============================================================================
# Start Message Management Handlers
# ============================================================================

@router.callback_query(F.data.startswith("acustom:set_start_msg:"))
async def cb_custom_set_start_message(callback: CallbackQuery, state: FSMContext) -> None:
    """Start message setting flow."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    await state.update_data(start_msg_custom_id=custom_id)
    await state.set_state(CustomStates.waiting_start_message)
    await callback.message.answer(
        "📝 <b>متن شروع کاستوم</b>\n\n"
        "لطفاً متنی که می‌خواهید هنگام شروع مسابقه برای شرکت‌کنندگان ارسال شود را وارد کنید.\n\n"
        "این متن برای تمام شرکت‌کنندگانی که ثبت‌نام قطعی کرده‌اند ارسال خواهد شد.\n\n"
        "یا برای انصراف /cancel را بزنید."
    )
    await callback.answer()


@router.message(CustomStates.waiting_start_message)
async def collect_start_message(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect start message."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
        return
    
    if not message.text:
        await message.answer("⚠️ لطفاً متن ارسال کنید.")
        return
    
    data = await state.get_data()
    custom_id = data.get("start_msg_custom_id")
    start_message = message.text.strip()
    
    # Show preview and ask for confirmation
    await state.update_data(start_message_text=start_message)
    await state.set_state(CustomStates.waiting_start_message_confirmation)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ تایید", callback_data=f"acustom:confirm_start_msg:{custom_id}"),
            types.InlineKeyboardButton(text="❌ انصراف", callback_data=f"acustom:cancel_start_msg:{custom_id}"),
        ]
    ])
    
    await message.answer(
        f"📋 <b>پیش‌نمایش متن شروع:</b>\n\n{start_message}\n\n"
        f"آیا این متن را تایید می‌کنید؟",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("acustom:confirm_start_msg:"))
async def cb_confirm_start_message(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Confirm and save start message."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    data = await state.get_data()
    start_message = data.get("start_message_text")
    
    if not start_message:
        await state.clear()
        await callback.answer("خطا: متن یافت نشد", show_alert=True)
        return
    
    cs = CustomService(uow)
    try:
        await cs.set_start_message(custom_id, start_message)
        await uow.flush()

        await uow.commit()
        
        # Log action
        api = AdminService(uow)
        await api.log_action(user, LogAction.CUSTOM_UPDATE, target_id=custom_id, description="تنظیم متن شروع")
        await uow.flush()

        await uow.commit()
        
        await state.clear()
        await callback.answer("✅ متن شروع ذخیره شد", show_alert=True)
        
        # Refresh view
        custom = await cs.get_custom(custom_id)
        if custom:
            await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))
    except ValueError as e:
        await state.clear()
        await callback.answer(f"❌ خطا: {e}", show_alert=True)


@router.callback_query(F.data.startswith("acustom:cancel_start_msg:"))
async def cb_cancel_start_message(callback: CallbackQuery, state: FSMContext, uow) -> None:
    """Cancel start message setting."""
    parts = callback.data.split(":", 2)
    custom_id = parts[2] if len(parts) >= 3 else None
    
    await state.clear()
    await callback.answer("❌ عملیات لغو شد")
    
    if custom_id:
        cs = CustomService(uow)
        custom = await cs.get_custom(custom_id)
        if custom:
            await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))


@router.callback_query(F.data.startswith("acustom:clear_start_msg:"))
async def cb_clear_start_message(callback: CallbackQuery, uow, user: User) -> None:
    """Clear start message."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    cs = CustomService(uow)
    await cs.clear_start_message(custom_id)
    await uow.flush()

    await uow.commit()
    
    # Log action
    api = AdminService(uow)
    await api.log_action(user, LogAction.CUSTOM_UPDATE, target_id=custom_id, description="حذف متن شروع")
    await uow.flush()

    await uow.commit()
    
    await callback.answer("✅ متن شروع حذف شد", show_alert=True)
    
    # Refresh view
    custom = await cs.get_custom(custom_id)
    if custom:
        await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))


# ============================================================================
# Start Custom Handler
# ============================================================================

@router.callback_query(F.data.startswith("acustom:start:"))
async def cb_start_custom(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Start a custom tournament."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    cs = CustomService(uow)
    custom = await cs.get_custom(custom_id)
    
    if not custom:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    
    # Check if start message is set
    if not custom.start_message:
        # Ask for confirmation
        await state.update_data(start_custom_id=custom_id)
        await state.set_state(CustomStates.waiting_start_confirmation)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ شروع بدون متن", callback_data=f"acustom:confirm_start:{custom_id}"),
                types.InlineKeyboardButton(text="❌ انصراف", callback_data=f"acustom:cancel_start:{custom_id}"),
            ]
        ])
        
        await callback.message.answer(
            "⚠️ <b>هشدار</b>\n\n"
            "متن شروع برای این کاستوم تنظیم نشده است.\n\n"
            "آیا می‌خواهید بدون ارسال متن شروع، مسابقه را آغاز کنید؟",
            reply_markup=kb
        )
        await callback.answer()
    else:
        # Start directly
        await _do_start_custom(callback, custom_id, uow, user, bot=callback.bot)


@router.callback_query(F.data.startswith("acustom:confirm_start:"))
async def cb_confirm_start_custom(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Confirm start without start message."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    await state.clear()
    await _do_start_custom(callback, custom_id, uow, user, bot=callback.bot)


@router.callback_query(F.data.startswith("acustom:cancel_start:"))
async def cb_cancel_start_custom(callback: CallbackQuery, state: FSMContext, uow) -> None:
    """Cancel start custom."""
    parts = callback.data.split(":", 2)
    custom_id = parts[2] if len(parts) >= 3 else None
    
    await state.clear()
    await callback.answer("❌ عملیات لغو شد")
    
    if custom_id:
        cs = CustomService(uow)
        custom = await cs.get_custom(custom_id)
        if custom:
            await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))


async def _do_start_custom(callback: CallbackQuery, custom_id: str, uow, user: User, bot=None) -> None:
    """Execute start custom logic."""
    cs = CustomService(uow)
    
    try:
        custom, result = await cs.start_custom(custom_id, user.id, bot=bot)
        
        if not custom:
            await callback.answer(f"❌ خطا: {result.get('error', 'خطای نامشخص')}", show_alert=True)
            return
        
        await uow.flush()

        
        await uow.commit()
        
        # Log action
        api = AdminService(uow)
        await api.log_action(user, LogAction.CUSTOM_START, target_id=custom_id, description="شروع کاستوم")
        await uow.flush()

        await uow.commit()
        
        # Show success message
        sent = result.get("sent", 0)
        failed = result.get("failed", 0)
        
        success_text = (
            f"🚀 <b>کاستوم شروع شد</b>\n\n"
            f"📨 ارسال پیام شروع:\n"
            f"✅ موفق: {sent}\n"
        )
        if failed > 0:
            success_text += f"❌ ناموفق: {failed}\n"
        
        await callback.answer("✅ کاستوم شروع شد", show_alert=True)
        await safe_edit_text(callback, success_text + "\n" + _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id, custom))
        
    except ValueError as e:
        await callback.answer(f"❌ خطا: {e}", show_alert=True)


# ============================================================================
# Postpone Custom Handler
# ============================================================================

@router.callback_query(F.data.startswith("acustom:postpone:"))
async def cb_postpone_custom(callback: CallbackQuery, state: FSMContext) -> None:
    """Start postpone flow."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("کاستوم یافت نشد", show_alert=True)
        return
    custom_id = parts[2]
    
    await state.update_data(postpone_custom_id=custom_id)
    await state.set_state(CustomStates.waiting_postpone_date)
    await callback.message.answer(
        "⏰ <b>عقب انداختن کاستوم</b>\n\n"
        "لطفاً تاریخ جدید را وارد کنید (فرمت: YYYY-MM-DD)\n"
        "مثال: 2026-09-15\n\n"
        "یا برای انصراف /cancel را بزنید."
    )
    await callback.answer()


@router.message(CustomStates.waiting_postpone_date)
async def collect_postpone_date(message: Message, state: FSMContext) -> None:
    """Collect new date for postpone."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
        return
    
    if not message.text:
        await message.answer("⚠️ لطفاً تاریخ را به فرمت YYYY-MM-DD وارد کنید.")
        return
    
    try:
        new_date = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        await state.update_data(postpone_new_date=new_date)
        await state.set_state(CustomStates.waiting_postpone_time)
        await message.answer(
            "🕐 حالا ساعت جدید را وارد کنید (فرمت: HH:MM)\n"
            "مثال: 20:00\n\n"
            "یا برای رد کردن این مرحله /skip را بزنید."
        )
    except ValueError:
        await message.answer("⚠️ فرمت تاریخ صحیح نیست. لطفاً به فرمت YYYY-MM-DD وارد کنید.")


@router.message(CustomStates.waiting_postpone_time)
async def collect_postpone_time(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect new time for postpone."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ عملیات لغو شد.")
        return
    
    data = await state.get_data()
    custom_id = data.get("postpone_custom_id")
    new_date = data.get("postpone_new_date")
    
    new_time = None
    if message.text != "/skip":
        new_time = message.text.strip()
        # Basic validation
        if not (len(new_time) == 5 and new_time[2] == ":"):
            await message.answer("⚠️ فرمت ساعت صحیح نیست. لطفاً به فرمت HH:MM وارد کنید یا /skip را بزنید.")
            return
    
    cs = CustomService(uow)
    try:
        custom = await cs.postpone_custom(custom_id, new_date=new_date, new_time=new_time)
        await uow.flush()

        await uow.commit()
        
        # Log action
        api = AdminService(uow)
        await api.log_action(user, LogAction.CUSTOM_UPDATE, target_id=custom_id, description=f"عقب انداختن به {new_date} {new_time or ''}")
        await uow.flush()

        await uow.commit()
        
        await state.clear()
        await message.answer(
            "✅ <b>کاستوم با موفقیت عقب انداخته شد</b>\n\n"
            f"📅 تاریخ جدید: {new_date.strftime('%Y-%m-%d')}\n"
            f"🕐 ساعت جدید: {new_time or 'تغییر نکرد'}",
            reply_markup=custom_admin_detail_keyboard(custom_id, custom)
        )
        
    except ValueError as e:
        await state.clear()
        await message.answer(f"❌ خطا: {e}")