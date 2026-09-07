"""User 'My Account' dashboard handlers."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, home_button
from bot.keyboards.dashboard import (
    dashboard_menu_keyboard,
    dashboard_orders_keyboard,
    orders_list_keyboard,
    wishlist_keyboard,
)
from bot.models.user import User
from bot.services.dashboard import UserDashboardService
from bot.states import DashboardStates, EditInfoStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="my_account")
logger = logging.getLogger(__name__)

PAGE_SIZE = 8


def _registered(user: User) -> str:
    if user.created_at:
        return user.created_at.strftime("%Y-%m-%d")
    return "—"


# --- Menu ---------------------------------------------------------------- #
@router.message(F.text.lower().startswith("/account") or F.text.lower() in ("/panel", "/profile"))
async def cmd_account(message: Message, uow, user: User) -> None:
    await _render_menu(message, uow, user, edit=False)


@router.callback_query(F.data == "dash:menu")
async def cb_dash_menu(callback: CallbackQuery, uow, user: User) -> None:
    await _render_menu(callback, uow, user)


async def _render_menu(event, uow, user: User, edit: bool = True) -> None:
    dsvc = UserDashboardService(uow)
    ov = await dsvc.overview(user)
    text = (
        "👤 <b>حساب من</b>\n\n"
        f"🆔 آیدی: <code>{user.telegram_id}</code>\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n"
        f"📅 عضویت: {_registered(user)}\n\n"
        f"📦 سفارش: {ov['total_orders']} (جاری {ov['active_orders']})\n"
        f"💳 کیف پول: <b>{format_price(ov['wallet_balance'])} تومان</b>\n"
        f"🎖 امتیاز: {ov['reward_points']}\n"
        f"💖 علاقه‌مندی: {ov['wishlist_count']}\n"
        f"🎫 تیکت باز: {ov['open_tickets']}\n\n"
        "انتخاب بخش:"
    )
    if edit:
        await event.message.edit_text(text, reply_markup=dashboard_menu_keyboard())
        if hasattr(event, "answer"):
            await event.answer()
    else:
        await event.answer(text, reply_markup=dashboard_menu_keyboard())


# --- Profile ------------------------------------------------------------- #
@router.callback_query(F.data == "dash:profile")
async def cb_profile(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    info = await dsvc.profile_info(user)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ ویرایش نام", callback_data="dash:edit:first")],
        [types.InlineKeyboardButton(text="🎁 کد رفرال", callback_data="dash:referral")],
        [back_button("dash:menu")],
    ])
    await safe_edit_text(callback, 
        "👤 <b>پروفایل</b>\n\n"
        f"👤 نام: {info['first_name'] or '—'} {info['last_name'] or ''}\n"
        f"👤 یوزرنیم: @{info['username'] or '-'}\n"
        f"🆔 آیدی: <code>{info['telegram_id']}</code>\n"
        f"📅 ثبت‌نام: {info['registered_at'].strftime('%Y-%m-%d') if info['registered_at'] else '—'}\n"
        f"💰 کل خرید: {format_price(user.total_spent)} تومان\n",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "dash:edit:first")
async def cb_edit_first(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DashboardStates.edit_first_name)
    await callback.message.answer("نام خود را ارسال کنید:")
    await callback.answer()


@router.message(DashboardStates.edit_first_name)
async def do_edit_first(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text or not message.text.strip():
        await message.answer("⚠️ نام خالی است:")
        return
    await UserDashboardService(uow).edit_profile(user, first_name=message.text.strip())
    await state.set_state(DashboardStates.edit_last_name)
    await message.answer("✅ نام ذخیره شد. نام خانوادگی را ارسال کنید (یا /skip):")


@router.message(DashboardStates.edit_last_name)
async def do_edit_last(message: Message, state: FSMContext, uow, user: User) -> None:
    if message.text and not message.text.startswith("/skip"):
        await UserDashboardService(uow).edit_profile(user, last_name=message.text.strip())
    await state.clear()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("dash:menu")]])
    await message.answer("✅ پروفایل به‌روزرسانی شد.", reply_markup=kb)


# --- Orders -------------------------------------------------------------- #
@router.callback_query(F.data == "dash:orders")
async def cb_orders(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "📦 <b>سفارش‌ها</b>", reply_markup=dashboard_orders_keyboard())
    await callback.answer()


async def _list_orders(callback: CallbackQuery, uow, user: User, statuses) -> None:
    dsvc = UserDashboardService(uow)
    orders = await dsvc.order_history(user, statuses, PAGE_SIZE)
    total = len(await dsvc.order_history(user, statuses, 100))
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if not orders:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("dash:orders")]])
        await safe_edit_text(callback, "سفارشی یافت نشد.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, 
        "📦 <b>سفارش‌ها</b>",
        reply_markup=orders_list_keyboard(orders, "orders", 0, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data == "dash:orders:current")
async def cb_orders_current(callback: CallbackQuery, uow, user: User) -> None:
    from bot.services.dashboard import ACTIVE_STATUSES
    await _list_orders(callback, uow, user, ACTIVE_STATUSES)


@router.callback_query(F.data == "dash:orders:completed")
async def cb_orders_completed(callback: CallbackQuery, uow, user: User) -> None:
    from bot.services.dashboard import COMPLETED_STATUSES
    await _list_orders(callback, uow, user, COMPLETED_STATUSES)


@router.callback_query(F.data == "dash:orders:cancelled")
async def cb_orders_cancelled(callback: CallbackQuery, uow, user: User) -> None:
    from bot.services.dashboard import CANCELLED_STATUSES
    await _list_orders(callback, uow, user, CANCELLED_STATUSES)


# --- Wishlist ------------------------------------------------------------- #
@router.callback_query(F.data == "dash:wishlist")
async def cb_wishlist(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    items = await dsvc.list_wishlist(user)
    if not items:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
        await safe_edit_text(callback, "💖 علاقه‌مندی شما خالی است.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "💖 <b>علاقه‌مندی‌ها</b>", reply_markup=wishlist_keyboard(items))
    await callback.answer()


@router.callback_query(F.data.startswith("dash:wishlist:view:"))
async def cb_wishlist_view(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    item_id = parts[3]
    dsvc = UserDashboardService(uow)
    items = await dsvc.list_wishlist(user)
    item = next((i for i in items if i.id == item_id), None)
    if not item:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"dash:wishlist_del:{item_id}")],
        [back_button("dash:wishlist")],
    ])
    await safe_edit_text(callback, 
        f"💖 <b>{item.title}</b>\n💰 قیمت: {format_price(item.price)} تومان",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dash:wishlist_del:"))
async def cb_wishlist_del(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("آیتم یافت نشد", show_alert=True)
        return
    item_id = parts[2]
    dsvc = UserDashboardService(uow)
    await dsvc.remove_wishlist(item_id)
    await uow.flush()

    await uow.commit()
    await callback.answer("حذف شد")
    await cb_wishlist(callback, uow, user)


# --- Payments / receipts -------------------------------------------------- #
@router.callback_query(F.data == "dash:payments")
async def cb_payments(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    payments = await dsvc.payment_history(user, limit=10)
    if not payments:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
        await safe_edit_text(callback, "💳 پرداختی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    lines = ["💳 <b>پرداخت‌ها</b>\n"]
    for p in payments:
        ts = p.created_at.strftime("%m-%d %H:%M") if p.created_at else ""
        lines.append(f"{ts} | {format_price(p.amount)} تومان | {p.status.value}")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
    await _simple_edit(callback, "\n".join(lines), kb)
    await callback.answer()


# --- Tickets -------------------------------------------------------------- #
@router.callback_query(F.data == "dash:tickets")
async def cb_tickets(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    tickets = await dsvc.ticket_history(user, limit=10)
    if not tickets:
        await safe_edit_text(callback, "🎫 تیکتی ثبت نشده است.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
        await callback.answer()
        return
    lines = ["🎫 <b>تیکت‌ها</b>\n"]
    for t in tickets:
        if t.ticket_category:
            lines.append(f"• {t.ticket_category.name} — {t.status.value}")
    await _simple_edit(callback, "\n".join(lines),
        types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
    await callback.answer()


# --- Tournaments ---------------------------------------------------------- #
@router.callback_query(F.data == "dash:tournaments")
async def cb_tournaments(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    results = await dsvc.tournament_results(user)
    if not results:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
        await safe_edit_text(callback, "🎮 ثبت‌نامی در کاستوم ندارید.", reply_markup=kb)
        await callback.answer()
        return
    lines = ["🎮 <b>کاستوم‌ها و نتایج</b>\n"]
    for r in results:
        icon = "🏆" if r["winner"] else "▫️"
        lines.append(f"{icon} {r['title']} — {r['result']}")
    await _simple_edit(callback, "\n".join(lines),
        types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
    await callback.answer()


# --- Downloads / purchases ------------------------------------------------ #
@router.callback_query(F.data == "dash:downloads")
async def cb_downloads(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    products = await dsvc.purchased_products(user)
    configs = await dsvc.purchased_configs(user)
    dl = await dsvc.downloads(user)
    lines = ["⬇️ <b>خروجی‌ها</b>\n", "🛒 <b>محصولات خریداری شده:</b>"]
    for p in products[:10]:
        lines.append(f"• {p['title']}")
    lines.append("\n⚡ <b>کانفیگ·های خریداری شده:</b>")
    for c in configs[:10]:
        lines.append(f"• {c['title']}")
    if dl:
        lines.append("\n📦 <b>فایل‌های قابل دانلود:</b>")
        for d in dl[:10]:
            lines.append(f"• {d['title']}")
    await _simple_edit(callback, "\n".join(lines),
        types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
    await callback.answer()


# --- Wallet --------------------------------------------------------------- #
@router.callback_query(F.data == "dash:wallet")
async def wallet_placeholder(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    ledger = await dsvc.wallet_ledger(user, 10)
    lines = [f"👛 <b>کیف پول</b>\n\n💰 مانده: <b>{format_price(user.wallet_balance)} تومان</b>\n"
            f"🎖 امتیاز: {user.reward_points}\n"]
    for t in ledger:
        sign = '+' if t.type.value in ('deposit','reward','refund','topup','admin_credit') else '-'
        ts = t.created_at.strftime('%m-%d %H:%M') if t.created_at else '?'
        lines.append(f"• {ts} {sign}{format_price(abs(t.amount))} {t.type.value}")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💰 شارژ حساب", callback_data="tu:menu")],
        [home_button()],
    ])
    await _simple_edit(callback, "\n".join(lines), kb)
    await callback.answer()


# --- Achievements --------------------------------------------------------- #
@router.callback_query(F.data == "dash:achievements")
async def cb_achievements(callback: CallbackQuery, uow, user: User) -> None:
    dsvc = UserDashboardService(uow)
    badges = await dsvc.all_badges()
    earned = {a.badge_key for a in await dsvc.earned_badges(user)}
    lines = ["🎖 <b>دستاوردها</b>\n"]
    for b in badges:
        mark = b.icon if b.key in earned else "🔒"
        lines.append(f"{mark} {b.name} — {b.description}")
    await _simple_edit(callback, "\n".join(lines),
        types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
    await callback.answer()


# --- Referral ------------------------------------------------ #
@router.callback_query(F.data == "dash:referral")
async def cb_referral(callback: CallbackQuery, uow, user: User) -> None:
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
    await safe_edit_text(callback, 
        "🎁 <b>رفرال</b>\n\n"
        f"🔑 کد شما: <code>{user.referral_code}</code>\n"
        f"🔗 لینک دعوت: {user.referral_code}\n\n"
        "این کد را هنگام شروع به دوستان خود بدهید.",
        reply_markup=kb,
    )
    await callback.answer()


async def _simple_edit(callback: CallbackQuery, text: str, kb) -> None:
    await safe_edit_text(callback, text, reply_markup=kb)

# --- My Info --------------------------------------------------------------- #
@router.callback_query(F.data == "dash:myinfo")
async def cb_my_info(callback: CallbackQuery, uow, user: User) -> None:
    """Show current user info with edit options."""
    from bot.keyboards.dashboard import my_info_keyboard
    text = (
        "📝 <b>اطلاعات من</b>\n\n"
        f"👤 نام: {user.customer_name or user.display_name or '—'}\n"
        f"📧 ایمیل: {user.email or '—'}\n"
        f"📱 تلفن: {getattr(user, 'phone', None) or '—'}\n"
        f"🔑 رمز عبور: {'••••••' if user.password else '—'}\n\n"
        "برای ویرایش هر بخش، دکمه مربوطه را بزنید:"
    )
    await safe_edit_text(callback, text, reply_markup=my_info_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("myinfo:edit:"))
async def cb_edit_info_field(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Start editing a specific info field."""
    from bot.states import EditInfoStates
    field = callback.data.split(":")[-1]
    
    field_labels = {
        "email": ("📧 ایمیل جدید", EditInfoStates.waiting_new_email),
        "phone": ("📱 شماره تلفن جدید", EditInfoStates.waiting_new_phone),
        "name": ("👤 نام جدید", EditInfoStates.waiting_new_name),
        "password": ("🔑 رمز عبور جدید", EditInfoStates.waiting_new_password),
    }
    
    if field not in field_labels:
        await callback.answer("فیلد نامعتبر", show_alert=True)
        return
    
    label, fsm_state = field_labels[field]
    await state.update_data(edit_field=field)
    await state.set_state(fsm_state)
    await callback.message.answer(f"{label} را وارد کنید:")
    await callback.answer()


@router.message(EditInfoStates.waiting_new_email)
async def do_edit_email(message: Message, state: FSMContext, uow, user: User) -> None:
    """Update user email (self or admin editing another user)."""
    import re
    data = await state.get_data()
    target_id = data.get("admin_edit_user_id") or user.id
    
    email = message.text.strip() if message.text else ""
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        await message.answer("⚠️ ایمیل نامعتبر است. دوباره وارد کنید:")
        return
    
    us = UserService(uow)
    await us.update_user(target_id, email=email)
    await uow.commit()
    await state.clear()
    
    if data.get("admin_edit_user_id"):
        await message.answer(f"✅ ایمیل کاربر به <b>{email}</b> تغییر یافت.")
    else:
        await message.answer(f"✅ ایمیل به <b>{email}</b> تغییر یافت.")


@router.message(EditInfoStates.waiting_new_phone)
async def do_edit_phone(message: Message, state: FSMContext, uow, user: User) -> None:
    """Update user phone (self or admin editing another user)."""
    data = await state.get_data()
    target_id = data.get("admin_edit_user_id") or user.id
    
    phone = message.text.strip() if message.text else ""
    if len(phone) < 8:
        await message.answer("⚠️ شماره تلفن نامعتبر است. دوباره وارد کنید:")
        return
    
    us = UserService(uow)
    await us.update_user(target_id, phone=phone)
    await uow.commit()
    await state.clear()
    
    if data.get("admin_edit_user_id"):
        await message.answer(f"✅ شماره تلفن کاربر به <b>{phone}</b> تغییر یافت.")
    else:
        await message.answer(f"✅ شماره تلفن به <b>{phone}</b> تغییر یافت.")


@router.message(EditInfoStates.waiting_new_name)
async def do_edit_name(message: Message, state: FSMContext, uow, user: User) -> None:
    """Update user name (self or admin editing another user)."""
    data = await state.get_data()
    target_id = data.get("admin_edit_user_id") or user.id
    
    name = message.text.strip() if message.text else ""
    if not name or len(name) < 2:
        await message.answer("⚠️ نام نامعتبر است. دوباره وارد کنید:")
        return
    
    us = UserService(uow)
    await us.update_user(target_id, customer_name=name)
    await uow.commit()
    await state.clear()
    
    if data.get("admin_edit_user_id"):
        await message.answer(f"✅ نام کاربر به <b>{name}</b> تغییر یافت.")
    else:
        await message.answer(f"✅ نام به <b>{name}</b> تغییر یافت.")


@router.message(EditInfoStates.waiting_new_password)
async def do_edit_password(message: Message, state: FSMContext, uow, user: User) -> None:
    """Update user password (self or admin editing another user)."""
    data = await state.get_data()
    target_id = data.get("admin_edit_user_id") or user.id
    
    password = message.text.strip() if message.text else ""
    if not password or len(password) < 4:
        await message.answer("⚠️ رمز عبور باید حداقل ۴ کاراکتر باشد. دوباره وارد کنید:")
        return
    
    us = UserService(uow)
    await us.update_user(target_id, password=password)
    await uow.commit()
    await state.clear()
    
    if data.get("admin_edit_user_id"):
        await message.answer("✅ رمز عبور کاربر تغییر یافت.")
    else:
        await message.answer("✅ رمز عبور تغییر یافت.")


@router.callback_query(F.data == "myinfo:request")
async def cb_info_change_request(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    """Start a free-text change request."""
    from bot.states import EditInfoStates
    await state.set_state(EditInfoStates.waiting_change_request)
    await callback.message.answer(
        "📨 <b>درخواست تغییر اطلاعات</b>\n\n"
        "لطفاً تغییرات مورد نظر خود را بنویسید.\n"
        "مثال: لطفاً ایمیل من رو به test@test.com تغییر بدید.\n\n"
        "این درخواست به ادمین ارسال می‌شود."
    )
    await callback.answer()


@router.message(EditInfoStates.waiting_change_request)
async def do_info_change_request(message: Message, state: FSMContext, uow, user: User) -> None:
    """Submit a change request to admin."""
    from bot.services.notification import NotificationService
    request_text = message.text.strip() if message.text else ""
    
    if not request_text:
        await message.answer("⚠️ لطفاً متن درخواست را وارد کنید:")
        return
    
    # Notify admins
    try:
        notifier = NotificationService(message.bot, uow)
        admin_text = (
            f"📨 <b>درخواست تغییر اطلاعات</b>\n\n"
            f"👤 کاربر: {user.display_name} ({user.telegram_id})\n"
            f"📝 درخواست:\n{request_text}\n\n"
            f"برای ویرایش اطلاعات این کاربر، از بخش «کاربران» اقدام کنید."
        )
        await notifier.send_to_admins(text=admin_text)
    except Exception as e:
        logger.warning(f"Failed to notify admins: {e}")
    
    await state.clear()
    await message.answer(
        "✅ درخواست شما ثبت شد و به ادمین ارسال گردید.\n"
        "به زودی اطلاعات شما تغییر خواهد کرد."
    )
