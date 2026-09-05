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
from bot.states import BroadcastStates, CustomStates
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
    if not data.get("title"):
        # The FSM data is gone (bot restarted, or the admin re-tapped an old
        # keyboard). Creating the row anyway crashed with a NOT NULL error and
        # poisoned the whole transaction.
        await state.clear()
        await callback.answer(
            "⚠️ اطلاعات این مرحله از بین رفته است. لطفاً دوباره از ابتدا شروع کنید.",
            show_alert=True,
        )
        return

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
    api = AdminService(uow)
    await api.log_action(user, LogAction.CUSTOM_CREATE, target_id=custom.id, description=f"ایجاد کاستوم {custom.title}")
    await uow.flush()
    await state.clear()

    text = (
        "✅ <b>کاستوم ایجاد شد</b>\n\n"
        f"🎮 عنوان: {custom.title}\n"
        f"💰 هزینه: {'رایگان' if custom.type.value == 'free' else format_price(custom.entry_fee)}\n"
        f"🎯 ظرفیت: {custom.max_capacity}\n\n"
        "برای فعال‌سازی ثبت‌نام، از منوی کاستوم گزینه «باز کردن ثبت‌نام» را بزنید."
    )
    await safe_edit_text(callback, text, reply_markup=custom_admin_detail_keyboard(custom.id))
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
    await safe_edit_text(callback, text, reply_markup=custom_admin_detail_keyboard(custom_id))
    await callback.answer()


def _custom_summary(custom) -> str:
    fee = "رایگان" if custom.type.value == "free" else f"{format_price(custom.entry_fee)} تومان"
    cap = f"{custom.current_players}/{custom.max_capacity}" if custom.max_capacity else str(custom.current_players)
    reg = "🟢 باز" if custom.registration_open else "🔴 بسته"
    status = {
        "draft": "پیش‌نویس", "registration_open": "باز ثبت", "registration_closed": "بسته ثبت",
        "in_progress": "در جریان", "completed": "تمام‌شده", "cancelled": "لغو"
    }.get(custom.status.value, custom.status.value)
    date = custom.event_date.strftime("%Y-%m-%d") if custom.event_date else "—"
    return (
        f"🎮 <b>{custom.title}</b>\n\n"
        f"📝 توضیحات: {custom.description or '—'}\n"
        f"📜 قوانین: {custom.rules or '—'}\n"
        f"📅 تاریخ: {date} {custom.event_time or ''}\n"
        f"🏆 جایزه: {custom.prize or '—'}\n"
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
    custom = await cs.set_registration_status(custom_id, True)
    await uow.flush()
    if custom:
        await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id))
    await callback.answer("ثبت‌نام باز شد")


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
    if custom:
        await safe_edit_text(callback, _custom_summary(custom), reply_markup=custom_admin_detail_keyboard(custom_id))
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
    api = AdminService(uow)
    await api.log_action(user, LogAction.CUSTOM_CANCEL, target_id=custom_id, description=reason)
    await uow.flush()

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
    await state.set_state(BroadcastStates.waiting_message)
    await callback.message.answer("📣 پیام اطلاع‌رسانی به شرکت‌کنندگان را بنویسید:")
    await callback.answer()


@router.message(BroadcastStates.waiting_message)
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
        # Show list of players to pick from
        keyboard = []
        for reg in registrations:
            label = f"{reg.codm_username}"
            keyboard.append([
                types.InlineKeyboardButton(text=label, callback_data=f"acustom:pick:{reg.id}")
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
    await _announce_winner(message.bot, uow, custom_id, user, custom)
    await state.clear()
    await message.answer("✅ برنده ثبت شد و اعلام شد.")


@router.callback_query(F.data.startswith("acustom:pick:"))
async def cb_custom_pick_winner(callback: CallbackQuery, uow, user: User) -> None:
    # callback: acustom:pick:<registration_id>
    # The custom id is derived from the registration (two UUIDs would exceed
    # Telegram's 64-byte callback_data limit -> BUTTON_DATA_INVALID).
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("بازیکن یافت نشد", show_alert=True)
        return
    reg_id = parts[2]
    cs = CustomService(uow)
    reg = await cs.get_registration(reg_id)
    if not reg:
        await callback.answer("بازیکن یافت نشد", show_alert=True)
        return
    custom_id = reg.custom_id
    custom = await cs.set_winner(custom_id, WinnerType.PLAYER, winner_user_id=reg.user_id)
    await uow.flush()
    await _announce_winner(callback.bot, uow, custom_id, user, custom)
    await callback.answer("برنده ثبت شد")
    await safe_edit_text(callback, "✅ برنده ثبت شد و اعلام شد.")


async def _announce_winner(bot, uow, custom_id: str, admin: User, custom) -> None:
    """Notify all participants and the winner."""
    cs = CustomService(uow)
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

# The next step of this flow is driven by inline buttons. Without this handler a
# typed answer was silently ignored and the flow looked frozen.
@router.message(CustomStates.waiting_category)
async def _hint_customstates_waiting_category(message: Message) -> None:
    await message.answer("برای انتخاب دسته‌بندی، روی یکی از دکمه‌های بالا بزنید 👆")
