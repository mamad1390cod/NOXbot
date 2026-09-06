"""Admin panel main handler (dashboard, stats, admin login)."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.admin import admin_panel_keyboard
from bot.models.user import User
from bot.services.admin import AdminService
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_panel")
logger = logging.getLogger(__name__)


class AdminLoginStates(StatesGroup):
    waiting_password = State()


@router.message(F.text == "/admin")
async def cmd_admin_login(message: Message, state: FSMContext) -> None:
    """Prompt the admin to enter the password to unlock the panel.

    The button for the panel is shown only to the owner (ADMIN_ID). For an
    extra layer of security, entering the panel requires the short password.
    Owner always unlocks directly without typing the password.
    """
    settings = get_settings()
    if message.from_user.id == settings.admin_id:
        # Owner bypasses the password gate.
        await message.answer(
            "👑 <b>پنل مدیریت</b>\n\nبرای ورود از دکمه مدیریت استفاده کنید.",
            reply_markup=_welcome_keyboard()
        )
        return
    await state.set_state(AdminLoginStates.waiting_password)
    await message.answer("🔐 لطفاً رمز عبور ادمین را وارد کنید:")


def _welcome_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👑 باز کردن پنل", callback_data="admin:panel")]
    ])


def admin_login_ready_keyboard() -> types.InlineKeyboardMarkup:
    return _welcome_keyboard()


@router.message(AdminLoginStates.waiting_password)
async def check_admin_password(message: Message, state: FSMContext, uow, user: User) -> None:
    password = message.text.strip()
    settings = get_settings()
    if password == settings.admin_password:
        await state.clear()
        kb = admin_login_ready_keyboard()
        await message.answer(
            "✅ رمز عبور صحیح بود. پنل مدیریت برای شما فعال شد.",
            reply_markup=kb,
        )
    else:
        # Anti-abuse: record a failed login attempt; lock after 5 fails.
        from bot.services.abuse import AntiAbuseService
        from bot.models.abuse import AbuseType, AutoActionType
        abuse = AntiAbuseService(uow)
        await abuse.record(AbuseType.BRUTE_FORCE_LOGIN, user=user, source="login")
        fails = await abuse.uow.abuse.count_for_user(user.id, AbuseType.BRUTE_FORCE_LOGIN, 10)
        if fails >= 5:
            await abuse._apply(AutoActionType.RATE_LIMIT, user, "brute force")
            await state.clear()
            await message.answer("🔒 به دلیل تلاش‌های ناموفق زیاد، ورود موقتاً قفل شد.")
            return
        await message.answer("❌ رمز عبور اشتباه است. دوباره تلاش کنید:")
        await state.set_state(AdminLoginStates.waiting_password)


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(callback: CallbackQuery, uow, user: User) -> None:
    """Open admin panel (dashboard)."""
    admin_service = AdminService(uow)
    stats = await admin_service.get_dashboard_stats()

    users = stats["users"]
    revenue = stats["revenue"]
    payments = stats["payments"]

    text = (
        "👑 <b>پنل مدیریت</b>\n\n"
        "📊 <b>آمار کلی</b>\n"
        f"👥 کل کاربران: {users['total']}\n"
        f"🆕 کاربران امروز: {users['new_today']}\n"
        f"💚 کاربران فعال: {users['active_week']}\n"
        f"🚫 بن‌شده: {users['banned']}\n\n"
        f"📦 محصولات: {stats['products_count']}  |  ⚡ کانفیگ‌ها: {stats['configs_count']}\n"
        f"🎮 کاستوم‌ها: {stats['customs_count']}\n\n"
        f"🧾 سفارشات: {revenue['total_orders']}\n"
        f"💰 درآمد کل: <b>{format_price(revenue['total_revenue'])} تومان</b>\n"
        f"💰 درآمد امروز: <b>{format_price(revenue['today_revenue'])} تومان</b>\n\n"
        f"💳 پرداخت‌ها — در انتظار: {payments['pending']} | تایید: {payments['approved']} | رد: {payments['rejected']}\n"
        f"🎫 تیکت‌های باز: {stats['tickets_open']}\n"
        f"⏳ سفارشات در انتظار: {stats['pending_orders']}\n"
    )
    await safe_edit_text(callback, text, reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery, uow, user: User) -> None:
    """Show detailed statistics."""
    admin_service = AdminService(uow)
    stats = await admin_service.get_dashboard_stats()

    text = (
        "📊 <b>آمار دقیق</b>\n\n"
        "👥 <b>کاربران</b>\n"
        f"کل: {stats['users']['total']}\n"
        f"جدید امروز: {stats['users']['new_today']}\n"
        f"فعال (۷ روز): {stats['users']['active_week']}\n"
        f"بن‌شده: {stats['users']['banned']}\n"
        f"ادمین‌ها: {stats['users']['admins']}\n\n"
        "🧾 <b>سفارشات و درآمد</b>\n"
        f"کل سفارشات: {stats['revenue']['total_orders']}\n"
        f"درآمد کل: {format_price(stats['revenue']['total_revenue'])} تومان\n"
        f"درآمد امروز: {format_price(stats['revenue']['today_revenue'])} تومان\n\n"
        "💳 <b>پرداخت‌ها</b>\n"
        f"در انتظار: {stats['payments']['pending']}\n"
        f"تایید شده: {stats['payments']['approved']}\n"
        f"رد شده: {stats['payments']['rejected']}\n\n"
        "📦 <b>موجودی‌ها</b>\n"
        f"محصولات: {stats['products_count']}\n"
        f"کانفیگ‌ها: {stats['configs_count']}\n"
        f"کاستوم‌ها: {stats['customs_count']}\n"
        f"تیکت‌های باز: {stats['tickets_open']}\n"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:panel")]
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin:logs")
async def cb_admin_logs(callback: CallbackQuery, uow, user: User) -> None:
    """Show recent admin logs."""
    admin_service = AdminService(uow)
    logs = await admin_service.get_logs(limit=20)
    if not logs:
        text = "📜 لاگی یافت نشد."
    else:
        lines = []
        for log in logs:
            action = log.action.value
            ts = log.created_at.strftime("%m-%d %H:%M") if log.created_at else ""
            admin_name = log.admin.username if log.admin else "?"
            session = log.session_id[:8] if log.session_id else ""
            entry = f"{ts} | @{admin_name} | {action}"
            if session:
                entry += f" [<code>{session}</code>]"
            entry += f" | {log.description or ''}"
            if log.old_data or log.new_data:
                entry += f"\n   قبل: {log.old_data}\n   بعد: {log.new_data}"
            lines.append(entry)
        text = "📜 <b>لاگ‌های اخیر</b>\n\n" + "\n".join(lines)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:panel")]
    ])
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()