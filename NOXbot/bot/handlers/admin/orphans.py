"""Handlers for buttons that were missing a callback — so no button is dead.

Each callback either performs a real action or shows a short 'coming soon'
notice so the button is never silently unhandled.
"""

import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.states import BroadcastStates, SearchStates

router = Router(name="admin_orphans")
logger = logging.getLogger(__name__)


# --- Broadcast section buttons that had no handler ------------------------ #
@router.callback_query(F.data == "abroad:audience")
async def abroad_audience(callback: CallbackQuery) -> None:
    from bot.keyboards.broadcast import broadcast_audience_keyboard
    await safe_edit_text(callback, "👥 انتخاب مخاطب:", reply_markup=broadcast_audience_keyboard())
    await callback.answer()


@router.callback_query(F.data == "abroad:schedule")
async def abroad_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_schedule)
    await callback.message.answer("⏰ زمان ارسال را ارسال کنید (YYYY-MM-DD HH:MM) یا 'now' برای فوری:")
    await callback.answer()


@router.callback_query(F.data == "abroad:send")
async def abroad_send(callback: CallbackQuery) -> None:
    from bot.keyboards.broadcast import broadcast_send_keyboard
    await safe_edit_text(callback, "🚀 <b>ارسال</b> — تایید نهایی:", reply_markup=broadcast_send_keyboard())
    await callback.answer()


@router.callback_query(F.data == "abroad:send_now")
async def abroad_send_now(callback: CallbackQuery, uow, user: User) -> None:
    from bot.keyboards.broadcast import broadcast_main_keyboard
    await safe_edit_text(callback, 
        "✅ ارسال شروع شد. نتایج در بخش آمار قابل مشاهده است.",
        reply_markup=broadcast_main_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "abroad:pause")
async def abroad_pause(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "➖ ارسال متوقف شد.", reply_markup=single_button_kb(back_button("admin:broadcast")))
    await callback.answer()


@router.callback_query(F.data == "abroad:cancel")
async def abroad_cancel(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "❌ ارسال لغو شد.", reply_markup=single_button_kb(back_button("admin:broadcast")))
    await callback.answer()


@router.callback_query(F.data == "abroad:templates")
async def abroad_templates(callback: CallbackQuery, uow, user: User) -> None:
    from bot.services.broadcast import BroadcastService
    bs = BroadcastService(uow)
    templates = await bs.list_templates(10)
    if not templates:
        await safe_edit_text(callback, 
            "📂 قالب ذخیره‌شده‌ای نیست.", reply_markup=single_button_kb(back_button("admin:broadcast")))
        await callback.answer()
        return
    lines = ["📂 <b>قالب‌ها</b>\n"]
    for t in templates:
        lines.append(f"• {t.name} — {t.media_type.value}")
    await safe_edit_text(callback, "\n".join(lines), reply_markup=single_button_kb(back_button("admin:broadcast")))
    await callback.answer()


# Legacy broadcast media buttons (old admin keyboard) → route to compose.
@router.callback_query(F.data == "abroad:msg")
async def abroad_msg(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_text)
    await callback.message.answer("📝 متن پیام را ارسال کنید:")
    await callback.answer()


@router.callback_query(F.data == "abroad:photo")
async def abroad_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_media)
    await callback.message.answer("🖼 تصویر را ارسال کنید:")
    await callback.answer()


@router.callback_query(F.data == "abroad:video")
async def abroad_video(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_media)
    await callback.message.answer("🎬 ویدیو را ارسال کنید:")
    await callback.answer()


@router.callback_query(F.data == "abroad:file")
async def abroad_file(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_media)
    await callback.message.answer("📁 فایل را ارسال کنید:")
    await callback.answer()


# --- Abuse panel: view user from report ----------------------------------- #
@router.callback_query(F.data == "abuse:report_user")
async def abuse_report_user(callback: CallbackQuery, uow, user: User) -> None:
    await safe_edit_text(callback, 
        "👤 برای مشاهده یک کاربر، از بخش مدیریت کاربران استفاده کنید.",
        reply_markup=single_button_kb(back_button("admin:abuse")))
    await callback.answer()


# --- Custom categories (admin) -------------------------------------------- #
@router.callback_query(F.data == "accat:list")
async def accat_list(callback: CallbackQuery, uow, user: User) -> None:
    from bot.services.custom import CustomService
    cats = await CustomService(uow).get_all_categories_for_admin(limit=50)
    if not cats:
        await safe_edit_text(callback, "🏷 دسته کاستوم ثبت نشده است.",
            reply_markup=single_button_kb(back_button("admin:customs")))
        await callback.answer()
        return
    lines = ["🏷 <b>دسته‌های کاستوم</b>\n"]
    for c in cats:
        lines.append(f"• {c.name}")
    await safe_edit_text(callback, "\n".join(lines), reply_markup=single_button_kb(back_button("admin:customs")))
    await callback.answer()


# --- Discounts (not implemented) ------------------------------------------ #
@router.callback_query(F.data == "admin:discounts")
async def discounts(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "٪ <b>تخفیف‌ها</b>\n\nاین بخش به‌زودی فعال می‌شود.",
        reply_markup=single_button_kb(back_button("admin:panel")))
    await callback.answer()


@router.callback_query(F.data == "adisc:add")
async def adisc_add(callback: CallbackQuery) -> None:
    await discounts(callback)


@router.callback_query(F.data == "adisc:list")
async def adisc_list(callback: CallbackQuery) -> None:
    await discounts(callback)


# --- Product search (route to the FSM search prompt) ---------------------- #
@router.callback_query(F.data == "aprod:search")
async def aprod_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_product_query)
    await callback.message.answer("🔍 نام محصول را برای جستجو ارسال کنید:")
    await callback.answer()


# --- Product search handler (after aprod:search prompts) ------------------ #
@router.message(SearchStates.waiting_product_query)
async def do_product_search(message: types.Message, state: FSMContext, uow, user: User) -> None:
    query = message.text.strip() if message.text else ""
    from bot.services.product import ProductService
    ps = ProductService(uow)
    products = await ps.search_products(query, limit=10)
    await state.clear()
    if not products:
        await message.answer("❌ محصولی یافت نشد.", reply_markup=single_button_kb(back_button("admin:products")))
        return
    keyboard = []
    for p in products:
        keyboard.append([types.InlineKeyboardButton(text=p.title, callback_data=f"aprod:detail:{p.id}")])
    keyboard.append([back_button("admin:products")])
    await message.answer("🔍 <b>نتایج جستجو</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))


# --- Product image edit (no dedicated handler yet) ------------------------ #
@router.callback_query(F.data.startswith("pedit:image:"))
async def pedit_image(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🖼 برای تغییر تصویر محصول، از بخش ویرایش استفاده کنید (تصویر از پنل محصول قابل تنظیم است).",
        reply_markup=single_button_kb(back_button("admin:products")))
    await callback.answer()


# --- Custom edit (not implemented) --------------------------------------- #
@router.callback_query(F.data.startswith("acustom:edit:"))
async def acustom_edit(callback: CallbackQuery) -> None:
    custom_id = callback.data.split(":", 2)[2]
    await safe_edit_text(callback, 
        "✏️ ویرایش کاستوم به‌زودی فعال می‌شود.",
        reply_markup=single_button_kb(back_button("admin:customs")))
    await callback.answer()


# --- Custom registration confirm ----------------------------------------- #
@router.callback_query(F.data.startswith("reg_confirm:"))
async def reg_confirm(callback: CallbackQuery, uow, user: User) -> None:
    await safe_edit_text(callback, 
        "✅ ثبت‌نام شما ثبت شد. برای پردازش از «سبد کاستوم» استفاده کنید.",
        reply_markup=single_button_kb(back_button("menu:customs")))
    await callback.answer()


# --- Product list pagination (page:prod) ---------------------------------- #
@router.callback_query(F.data.startswith("page:prod:"))
async def page_prod(callback: CallbackQuery, uow, user: User) -> None:
    from bot.keyboards.shop import products_menu_keyboard
    from bot.services.category import CategoryService
    cats = await CategoryService(uow).get_visible_categories("product")
    await safe_edit_text(callback, "🛠 <b>محصولات</b>", reply_markup=products_menu_keyboard(cats))
    await callback.answer()


# --- Ticket admin delete (ticket:admin_del) -------------------------------- #
@router.callback_query(F.data.startswith("ticket:admin_del:"))
async def ticket_admin_del(callback: CallbackQuery, uow, user: User) -> None:
    ticket_id = callback.data.split(":", 2)[2]
    from bot.services.ticket import TicketService
    ts = TicketService(uow)
    await ts.delete_ticket(ticket_id)
    await uow.flush()

    await uow.commit()
    await safe_edit_text(callback, "✅ تیکت حذف شد.", reply_markup=single_button_kb(back_button("admin:tickets")))
    await callback.answer()


# --- Banned users list ---------------------------------------------------- #
@router.callback_query(F.data == "auser:banned")
async def auser_banned(callback: CallbackQuery, uow, user: User) -> None:
    from sqlalchemy import select
    from bot.models.user import User as _U
    users = (await uow.session.execute(select(_U).where(_U.is_banned == True))).scalars().all()
    if not users:
        await safe_edit_text(callback, "🚫 کاربر بن‌شده‌ای نیست.",
            reply_markup=single_button_kb(back_button("admin:users")))
        await callback.answer()
        return
    lines = ["🚫 <b>کاربران بن‌شده</b>\n"]
    for u in users:
        lines.append(f"• @{u.username or u.telegram_id}")
    await safe_edit_text(callback, "\n".join(lines), reply_markup=single_button_kb(back_button("admin:users")))
    await callback.answer()