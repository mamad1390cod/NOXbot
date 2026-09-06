"""Support / ticket handlers (user side)."""

from datetime import datetime
from bot.utils.editing import safe_edit_text

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, cancel_button
from bot.keyboards.ticket import my_tickets_keyboard, ticket_categories_keyboard, ticket_detail_keyboard, ticket_menu_keyboard
from bot.models.ticket import TicketPriority
from bot.models.user import User
from bot.services.notification import NotificationService
from bot.services.ticket import TicketService
from bot.states import TicketStates
from bot.texts import TICKET_CREATED

router = Router(name="support")


@router.callback_query(F.data == "menu:support")
async def cb_support(callback: CallbackQuery, uow, user: User) -> None:
    """Show support menu."""
    await safe_edit_text(callback, 
        "📨 <b>پشتیبانی</b>\n\n"
        "برای ثبت تیکت جدید یا مشاهده تیکت‌های خود یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=ticket_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "ticket:new")
async def cb_ticket_new(callback: CallbackQuery, uow, user: User) -> None:
    """Show ticket categories to choose from."""
    ticket_service = TicketService(uow)
    categories = await ticket_service.get_active_categories()
    if not categories:
        await callback.answer("در حال حاضر دسته‌بندی تیکتی موجود نیست", show_alert=True)
        return
    await safe_edit_text(callback, 
        "📩 <b>ثبت تیکت جدید</b>\n\nدسته‌بندی مورد نظر را انتخاب کنید:",
        reply_markup=ticket_categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tick_cat:"))
async def cb_ticket_category_chosen(
    callback: CallbackQuery,
    uow, user: User,
    state: FSMContext,
) -> None:
    """User chose a ticket category; collect message."""
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    category_id = parts[1]
    await state.set_data({"ticket_category_id": category_id})
    await state.set_state(TicketStates.waiting_message)
    await safe_edit_text(callback, 
        "📝 <b>پیام خود را بنویسید</b>\n\n"
        "لطفاً شرح مشکل یا درخواست خود را بنویسید:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button()]]),
    )
    await callback.answer()


@router.message(TicketStates.waiting_message)
async def collect_ticket_message(
    message: Message,
    uow, user: User,
    state: FSMContext,
) -> None:
    msg = message.text.strip()
    if not msg:
        await message.answer("⚠️ لطفاً متن پیام را بنویسید:")
        return

    data = await state.get_data()
    category_id = data.get("ticket_category_id")

    ticket_service = TicketService(uow)
    category = await ticket_service.get_category(category_id) if category_id else None
    try:
        ticket = await ticket_service.create_ticket(
            user_id=user.id,
            category_id=category_id,
            subject=category.name if category else "تیکت",
            message=msg,
            priority=TicketPriority.NORMAL,
        )
    except Exception as e:
        await message.answer("❌ خطا در ایجاد تیکت. لطفاً دوباره تلاش کنید.")
        await state.clear()
        return

    await uow.flush()


    await uow.commit()
    await state.clear()

    # Notify admin
    _now = datetime.now()
    from bot.keyboards.admin import ticket_admin_detail_keyboard
    text = (
        "🎫 <b>تیکت جدید</b>\n\n"
        f"🆔 آیدی تیکت: <code>{ticket.id[:8]}</code>\n"
        f"🆔 آیدی تلگرام: <code>{user.telegram_id}</code>\n"
        f"🆔 چت آیدی: <code>{user.telegram_id}</code>\n"
        f"👤 نام کاربری: @{user.username or '-'}\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n\n"
        f"📂 دسته: {category.name if category else '—'}\n"
        f"📝 پیام: {msg}\n\n"
        f"📅 تاریخ: {_now.strftime('%Y-%m-%d')}\n"
        f"🕒 زمان: {_now.strftime('%H:%M:%S')}"
    )
    notifier = NotificationService(message.bot, uow)
    await notifier.send_to_admins(
        text=text,
        reply_markup=ticket_admin_detail_keyboard(ticket.id),
    )

    await message.answer(
        TICKET_CREATED(),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[default_back()]]),
    )


def default_back():
    return back_button("menu:support")


@router.callback_query(F.data == "ticket:list")
async def cb_ticket_list(callback: CallbackQuery, uow, user: User) -> None:
    """Show user's tickets."""
    ticket_service = TicketService(uow)
    tickets = await ticket_service.get_user_tickets(user.id, limit=10)
    if not tickets:
        await callback.answer("هنوز تیکتی ثبت نکرده‌اید", show_alert=True)
        return
    await safe_edit_text(callback, 
        "📋 <b>تیکت‌های شما</b>",
        reply_markup=my_tickets_keyboard(tickets),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:view:"))
async def cb_ticket_view(callback: CallbackQuery, uow, user: User) -> None:
    """View a single ticket."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    ticket_service = TicketService(uow)
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return

    status_map = {
        "open": "🟢 باز",
        "in_progress": "🟠 در حال بررسی",
        "waiting_user": "🔵 در انتظار شما",
        "closed": "🔴 بسته",
    }
    status = status_map.get(ticket.status.value, ticket.status.value)

    text = (
        f"🎫 <b>تیکت #{ticket.id[:8]}</b>\n\n"
        f"📂 دسته: {ticket.ticket_category.name if ticket.ticket_category else '—'}\n"
        f"📝 موضوع: {ticket.subject}\n"
        f"📊 وضعیت: {status}\n\n"
        f"💬 <b>پیام شما:</b>\n{ticket.message}\n\n"
        f"📅 ثبت: {ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else '—'}\n"
    )
    # Include admin replies
    for msg in ticket.messages:
        if msg.is_admin:
            text += f"\n👨💼 <b>پاسخ ادمین:</b>\n{msg.message}\n"

    await safe_edit_text(callback, 
        text,
        reply_markup=ticket_detail_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:reply:"))
async def cb_ticket_reply(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Begin replying to a ticket as the user."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    await state.set_data({"ticket_id": ticket_id})
    await state.set_state(TicketStates.reply_to_ticket)
    await callback.message.answer("📝 پیام پاسخ خود را بنویسید:")
    await callback.answer()


@router.message(TicketStates.reply_to_ticket)
async def user_ticket_reply(
    message: Message,
    uow, user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    ticket_service = TicketService(uow)
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.status.value == "closed":
        await message.answer("❌ این تیکت بسته شده است.")
        await state.clear()
        return
    await ticket_service.reply_to_ticket(
        ticket_id=ticket_id,
        user_id=user.id,
        message=message.text.strip(),
        is_admin=False,
    )
    await uow.flush()

    await uow.commit()
    await state.clear()

    # Notify admin
    _now = datetime.now()
    text = (
        f"💬 <b>پاسخ جدید به تیکت #{ticket_id[:8]}</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{user.telegram_id}</code>\n"
        f"👤 نام: {user.first_name or ''} {user.last_name or ''}\n\n"
        f"📝 پاسخ: {message.text}"
    )
    notifier = NotificationService(message.bot, uow)
    from bot.keyboards.admin import ticket_admin_detail_keyboard
    await notifier.send_to_admins(text=text, reply_markup=ticket_admin_detail_keyboard(ticket_id))
    await message.answer("✅ پاسخ شما ثبت شد.")


@router.callback_query(F.data.startswith("ticket:close:"))
async def cb_ticket_close(callback: CallbackQuery, uow, user: User) -> None:
    """Close a ticket (user-initiated)."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    ticket_service = TicketService(uow)
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    await ticket_service.close_ticket(ticket_id, admin_id=user.id)
    await uow.flush()

    await uow.commit()
    await callback.answer("تیکت بسته شد")
    await safe_edit_text(callback, "✅ <b>تیکت بسته شد.</b>")