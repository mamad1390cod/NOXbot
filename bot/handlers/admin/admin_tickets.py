"""Admin ticket management handlers."""

import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import admin_ticket_list_keyboard, admin_tickets_keyboard, ticket_admin_detail_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.ticket import TicketStatus
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.notification import NotificationService
from bot.services.ticket import TicketService
from bot.states import TicketStates
from bot.texts import TICKET_CLOSED

router = Router(name="admin_tickets")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:tickets")
async def cb_admin_tickets(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "🎫 <b>مدیریت تیکت‌ها</b>", reply_markup=admin_tickets_keyboard())
    await callback.answer()


@router.callback_query(F.data == "atick:open")
async def cb_tickets_open(callback: CallbackQuery, uow, user: User) -> None:
    ts = TicketService(uow)
    tickets = await ts.get_open_tickets(limit=30)
    if not tickets:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:tickets")]])
        await safe_edit_text(callback, "🎫 تیکت باز یافت نشد.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "🎫 <b>تیکت‌های باز</b>", reply_markup=admin_ticket_list_keyboard(tickets))
    await callback.answer()


@router.callback_query(F.data == "atick:closed")
async def cb_tickets_closed(callback: CallbackQuery, uow, user: User) -> None:
    ts = TicketService(uow)
    tickets = await ts.get_closed_tickets(limit=30)
    if not tickets:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:tickets")]])
        await safe_edit_text(callback, "🎫 تیکت بسته یافت نشد.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, "🎫 <b>تیکت‌های بسته</b>", reply_markup=admin_ticket_list_keyboard(tickets))
    await callback.answer()


@router.callback_query(F.data.startswith("atick:view:"))
async def cb_ticket_admin_view(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    ts = TicketService(uow)
    ticket = await ts.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    tuser = ticket.user
    status_map = {"open": "🟢 باز", "in_progress": "🟠 در حال بررسی", "waiting_user": "🔵 در انتظار کاربر", "closed": "🔴 بسته"}
    text = (
        f"🎫 <b>تیکت #{ticket.id[:8]}</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{tuser.telegram_id if tuser else '?'}</code>\n"
        f"👤 نام: {tuser.first_name or ''} {tuser.last_name or ''} (@{tuser.username or '-'})\n"
        f"📂 دسته: {ticket.ticket_category.name if ticket.ticket_category else '—'}\n"
        f"📊 وضعیت: {status_map.get(ticket.status.value, ticket.status.value)}\n\n"
        f"💬 <b>پیام:</b>\n{ticket.message}\n"
    )
    for msg in ticket.messages:
        if msg.is_admin:
            text += f"\n👨💼 <b>پاسخ ادمین:</b>\n{msg.message}\n"
        elif not msg.is_system and msg.message != ticket.message:
            text += f"\n👤 <b>پاسخ کاربر:</b>\n{msg.message}\n"
    await safe_edit_text(callback, text, reply_markup=ticket_admin_detail_keyboard(ticket_id))
    await callback.answer()


@router.callback_query(F.data.startswith("atick:reply:"))
async def cb_ticket_admin_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Begin replying to a ticket as the user."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    await state.set_data({"ticket_id": ticket_id})
    await state.set_state(TicketStates.waiting_admin_reply)
    await callback.message.answer("✍️ پاسخ ادمین را بنویسید:")
    await callback.answer()


@router.message(TicketStates.waiting_admin_reply)
async def do_ticket_admin_reply(
    message: Message,
    state: FSMContext,
    uow, user: User,
) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    reply_text = message.text.strip() if message.text else ""
    ts = TicketService(uow)
    ticket = await ts.get_ticket(ticket_id)
    if not ticket:
        await message.answer("تیکت یافت نشد")
        await state.clear()
        return

    await ts.reply_to_ticket(
        ticket_id=ticket_id,
        user_id=user.id,
        message=reply_text,
        is_admin=True,
    )
    await ts.update_ticket_status(ticket_id, TicketStatus.IN_PROGRESS)
    await uow.flush()

    api = AdminService(uow)
    await api.log_action(user, LogAction.TICKET_REPLY, target_id=ticket_id, description="پاسخ به تیکت")
    await uow.flush()

    # Notify the user
    if ticket.user:
        notifier = NotificationService(message.bot, uow)
        await notifier.notify_user(
            ticket.user.telegram_id,
            f"👨💼 <b>پاسخ ادمین به تیکت #{ticket_id[:8]}</b>\n\n{reply_text}",
        )
    await state.clear()
    await message.answer("✅ پاسخ ارسال شد.", reply_markup=single_button_kb(back_button("admin:tickets")))


@router.callback_query(F.data.startswith("atick:del:"))
async def cb_ticket_admin_delete(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    ts = TicketService(uow)
    await ts.delete_ticket(ticket_id)
    await uow.flush()
    await callback.answer("حذف شد")
    await safe_edit_text(callback, "✅ تیکت حذف شد.", reply_markup=single_button_kb(back_button("admin:tickets")))


@router.callback_query(F.data.startswith("ticket:close:"))
async def cb_ticket_close_shared(callback: CallbackQuery, uow, user: User) -> None:
    """Close a ticket (shared for user + admin)."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    ticket_id = parts[2]
    ts = TicketService(uow)
    ticket = await ts.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return

    await ts.close_ticket(ticket_id, admin_id=user.id)
    await uow.flush()

    # Notify user that ticket is closed
    if ticket.user:
        notifier = NotificationService(callback.bot, uow)
        await notifier.notify_user(ticket.user.telegram_id, TICKET_CLOSED())

    await callback.answer("تیکت بسته شد")
    await safe_edit_text(callback, "✅ تیکت بسته شد.")


@router.callback_query(F.data == "atick:search")
async def cb_ticket_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketStates.waiting_close_reason)
    await callback.message.answer("🔍 موضوع یا متن تیکت را جستجو کنید:")
    await callback.answer()


@router.message(TicketStates.waiting_close_reason)
async def do_ticket_search(message: Message, state: FSMContext, uow, user: User) -> None:
    query = message.text.strip() if message.text else ""
    ts = TicketService(uow)
    tickets = await ts.search_tickets(query, limit=20)
    await state.clear()
    if not tickets:
        await message.answer("❌ تیکتی یافت نشد.")
        return
    await message.answer("🎫 نتایج جستجو:", reply_markup=admin_ticket_list_keyboard(tickets))


@router.callback_query(F.data == "atick:export")
async def cb_ticket_export(callback: CallbackQuery) -> None:
    """Export tickets as CSV (via backup util)."""
    from bot.utils.backup import export_tickets_csv
    try:
        path = await export_tickets_csv()
    except Exception as e:
        logger.exception("Export failed: %s", e)
        await callback.answer("❌ خطا در خروجی گرفتن", show_alert=True)
        return
    # Send file to admin
    await callback.message.answer_document(types.FSInputFile(path))
    await callback.answer("خروجی ارسال شد")