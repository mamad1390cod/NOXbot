"""Admin handlers for ticket category management."""

import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.services.ticket import TicketService
from bot.states import AdminTicketCategoryStates
from bot.utils.editing import safe_edit_text
from bot.utils.format import format_price

router = Router(name="admin_ticket_categories")
logger = logging.getLogger(__name__)


def ticket_categories_keyboard(categories):
    """Build keyboard for ticket categories list."""
    keyboard = []
    for cat in categories:
        status = "🟢" if cat.is_active else "🔴"
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{status} {cat.emoji or ''} {cat.name}",
                callback_data=f"aticat:view:{cat.id}"
            )
        ])
    keyboard.append([
        types.InlineKeyboardButton(text="➕ افزودن دسته", callback_data="aticat:add"),
        types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:tickets"),
    ])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


def ticket_category_detail_keyboard(category_id, is_active):
    """Build keyboard for ticket category detail."""
    keyboard = [
        [
            types.InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"aticat:edit:{category_id}"),
            types.InlineKeyboardButton(
                text="🟢 فعال" if not is_active else "🔴 غیرفعال",
                callback_data=f"aticat:toggle:{category_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"aticat:delete:{category_id}"),
        ],
        [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="aticat:list")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "aticat:list")
async def cb_ticket_categories_list(callback: CallbackQuery, uow, user: User) -> None:
    """Show list of ticket categories."""
    ts = TicketService(uow)
    categories = await ts.uow.ticket_categories.get_all(limit=100)
    
    if not categories:
        text = "🎫 <b>دسته‌بندی تیکت‌ها</b>\n\nهیچ دسته‌بندی‌ای تعریف نشده است."
    else:
        text = f"🎫 <b>دسته‌بندی تیکت‌ها</b>\n\nتعداد: {len(categories)}"
    
    await safe_edit_text(callback, text, reply_markup=ticket_categories_keyboard(categories))
    await callback.answer()


@router.callback_query(F.data == "aticat:add")
async def cb_ticket_category_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start adding a new ticket category."""
    await state.set_state(AdminTicketCategoryStates.waiting_name)
    await callback.message.answer(
        "📝 <b>افزودن دسته‌بندی تیکت</b>\n\n"
        "نام دسته‌بندی را وارد کنید:\n"
        "مثال: خرابی کانفیگ"
    )
    await callback.answer()


@router.message(AdminTicketCategoryStates.waiting_name)
async def collect_ticket_category_name(message: Message, state: FSMContext) -> None:
    """Collect category name."""
    name = message.text.strip()
    if not name or len(name) > 255:
        await message.answer("⚠️ نام نامعتبر است. دوباره وارد کنید:")
        return
    
    await state.update_data(name=name)
    await state.set_state(AdminTicketCategoryStates.waiting_emoji)
    await message.answer(
        "🎨 حالا یک ایموجی برای این دسته انتخاب کنید (یا /skip):\n"
        "مثال: 🔧 یا ❌ یا 📧"
    )


@router.message(AdminTicketCategoryStates.waiting_emoji)
async def collect_ticket_category_emoji(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect category emoji and create category."""
    emoji = message.text.strip() if message.text and not message.text.startswith("/skip") else None
    
    data = await state.get_data()
    name = data.get("name")
    
    ts = TicketService(uow)
    try:
        category = await ts.create_category(
            name=name,
            emoji=emoji,
        )
        await uow.commit()
        
        await state.clear()
        await message.answer(
            f"✅ <b>دسته‌بندی ایجاد شد</b>\n\n"
            f"{emoji or ''} {name}\n\n"
            f"ID: <code>{category.id}</code>",
            reply_markup=single_button_kb(back_button("aticat:list"))
        )
    except Exception as e:
        logger.exception(f"Failed to create ticket category: {e}")
        await state.clear()
        await message.answer(
            f"❌ خطا در ایجاد دسته‌بندی: {e}",
            reply_markup=single_button_kb(back_button("aticat:list"))
        )


@router.callback_query(F.data.startswith("aticat:view:"))
async def cb_ticket_category_view(callback: CallbackQuery, uow, user: User) -> None:
    """View ticket category details."""
    category_id = callback.data.split(":")[2]
    ts = TicketService(uow)
    category = await ts.get_category(category_id)
    
    if not category:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    
    status = "🟢 فعال" if category.is_active else "🔴 غیرفعال"
    text = (
        f"🎫 <b>دسته‌بندی تیکت</b>\n\n"
        f"{category.emoji or ''} <b>{category.name}</b>\n\n"
        f"📊 وضعیت: {status}\n"
        f"🆔 ID: <code>{category.id}</code>\n"
        f"📅 ایجاد: {category.created_at.strftime('%Y-%m-%d') if category.created_at else '—'}\n"
    )
    
    await safe_edit_text(
        callback,
        text,
        reply_markup=ticket_category_detail_keyboard(category.id, category.is_active)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aticat:toggle:"))
async def cb_ticket_category_toggle(callback: CallbackQuery, uow, user: User) -> None:
    """Toggle ticket category active status."""
    category_id = callback.data.split(":")[2]
    ts = TicketService(uow)
    
    category = await ts.toggle_category_active(category_id)
    await uow.commit()
    
    if category:
        status = "فعال" if category.is_active else "غیرفعال"
        await callback.answer(f"دسته‌بندی {status} شد")
        # Refresh view
        await cb_ticket_category_view(callback, uow, user)
    else:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)


@router.callback_query(F.data.startswith("aticat:delete:"))
async def cb_ticket_category_delete(callback: CallbackQuery, uow, user: User) -> None:
    """Delete ticket category."""
    category_id = callback.data.split(":")[2]
    ts = TicketService(uow)
    
    try:
        await ts.delete_category(category_id)
        await uow.commit()
        await callback.answer("دسته‌بندی حذف شد")
        await cb_ticket_categories_list(callback, uow, user)
    except Exception as e:
        await callback.answer(f"خطا: {e}", show_alert=True)


@router.callback_query(F.data.startswith("aticat:edit:"))
async def cb_ticket_category_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start editing ticket category."""
    category_id = callback.data.split(":")[2]
    await state.update_data(category_id=category_id)
    await state.set_state(AdminTicketCategoryStates.waiting_edit_name)
    await callback.message.answer("📝 نام جدید دسته‌بندی را وارد کنید (یا /skip):")
    await callback.answer()


@router.message(AdminTicketCategoryStates.waiting_edit_name)
async def collect_edit_ticket_category_name(message: Message, state: FSMContext) -> None:
    """Collect new category name."""
    name = message.text.strip() if message.text and not message.text.startswith("/skip") else None
    
    if name and len(name) > 255:
        await message.answer("⚠️ نام خیلی طولانی است. دوباره وارد کنید:")
        return
    
    await state.update_data(new_name=name)
    await state.set_state(AdminTicketCategoryStates.waiting_edit_emoji)
    await message.answer("🎨 ایموجی جدید را وارد کنید (یا /skip):")


@router.message(AdminTicketCategoryStates.waiting_edit_emoji)
async def collect_edit_ticket_category_emoji(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect new emoji and update category."""
    emoji = message.text.strip() if message.text and not message.text.startswith("/skip") else None
    
    data = await state.get_data()
    category_id = data.get("category_id")
    new_name = data.get("new_name")
    
    ts = TicketService(uow)
    
    updates = {}
    if new_name:
        updates["name"] = new_name
    if emoji is not None:
        updates["emoji"] = emoji
    
    if updates:
        try:
            category = await ts.update_category(category_id, **updates)
            await uow.commit()
            
            await state.clear()
            await message.answer(
                f"✅ <b>دسته‌بندی ویرایش شد</b>\n\n"
                f"{category.emoji or ''} {category.name}",
                reply_markup=single_button_kb(back_button("aticat:list"))
            )
        except Exception as e:
            logger.exception(f"Failed to update ticket category: {e}")
            await state.clear()
            await message.answer(
                f"❌ خطا در ویرایش: {e}",
                reply_markup=single_button_kb(back_button("aticat:list"))
            )
    else:
        await state.clear()
        await message.answer(
            "ℹ️ تغییری اعمال نشد.",
            reply_markup=single_button_kb(back_button("aticat:list"))
        )
