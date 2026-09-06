"""Admin custom category management handlers."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.models.user import User
from bot.services.custom import CustomService
from bot.states import AdminCustomCategoryStates
from bot.utils.editing import safe_edit_text

router = Router(name="admin_custom_categories")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "accat:list")
async def cb_accat_list(callback: CallbackQuery, uow, user: User) -> None:
    """List all custom categories."""
    cs = CustomService(uow)
    cats = await cs.get_all_categories_for_admin(limit=50)
    
    if not cats:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ افزودن دسته", callback_data="accat:add")],
            [back_button("admin:customs")],
        ])
        await safe_edit_text(callback, "🏷 <b>دسته‌های کاستوم</b>\n\nهنوز دسته‌ای ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    
    lines = ["🏷 <b>دسته‌های کاستوم</b>\n"]
    keyboard = []
    for c in cats:
        status = "🟢" if c.is_active else "🔴"
        lines.append(f"{status} {c.name}")
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{status} {c.name}",
                callback_data=f"accat:view:{c.id}"
            )
        ])
    
    keyboard.append([types.InlineKeyboardButton(text="➕ افزودن دسته", callback_data="accat:add")])
    keyboard.append([back_button("admin:customs")])
    
    await safe_edit_text(callback, "\n".join(lines), 
                        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data == "accat:add")
async def cb_accat_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Start adding a new custom category."""
    await state.set_state(AdminCustomCategoryStates.waiting_name)
    await safe_edit_text(callback, 
        "🏷 <b>افزودن دسته کاستوم</b>\n\nنام دسته را وارد کنید:",
        reply_markup=single_button_kb(back_button("accat:list")))
    await callback.answer()


@router.message(AdminCustomCategoryStates.waiting_name)
async def collect_category_name(message: Message, state: FSMContext) -> None:
    """Collect category name."""
    name = message.text.strip() if message.text else ""
    
    if not name or len(name) < 2:
        await message.answer("⚠️ نام دسته باید حداقل 2 کاراکتر باشد. دوباره وارد کنید:")
        return
    
    await state.update_data(name=name)
    await state.set_state(AdminCustomCategoryStates.waiting_emoji)
    await message.answer(
        "🎨 <b>ایموجی (اختیاری)</b>\n\n"
        "یک ایموجی برای دسته وارد کنید (یا 'رد' برای رد کردن):\n"
        "مثال: 🎮 ⚽ 🎯"
    )


@router.message(AdminCustomCategoryStates.waiting_emoji)
async def collect_category_emoji(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect category emoji and save."""
    emoji = message.text.strip() if message.text else ""
    
    if emoji.lower() in ["رد", "skip", ""]:
        emoji = None
    elif len(emoji) > 10:
        await message.answer("⚠️ ایموجی خیلی طولانی است. دوباره وارد کنید:")
        return
    
    data = await state.get_data()
    name = data.get("name")
    
    cs = CustomService(uow)
    try:
        cat = await cs.create_category(
            name=name,
            emoji=emoji,
        )
        await uow.commit()
        await state.clear()
        
        text = f"✅ <b>دسته با موفقیت ایجاد شد</b>\n\n🏷 نام: {cat.name}\n"
        if emoji:
            text += f"🎨 ایموجی: {emoji}\n"
        
        await message.answer(text, reply_markup=single_button_kb(back_button("accat:list")))
    except Exception as e:
        logger.exception(f"Failed to create custom category: {e}")
        await state.clear()
        await message.answer(
            f"❌ خطا در ایجاد دسته: {e}",
            reply_markup=single_button_kb(back_button("accat:list"))
        )


@router.callback_query(F.data.startswith("accat:view:"))
async def cb_accat_view(callback: CallbackQuery, uow, user: User) -> None:
    """View category details."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    cat_id = parts[2]
    cs = CustomService(uow)
    cat = await cs.get_category(cat_id)
    
    if not cat:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    status = "🟢 فعال" if cat.is_active else "🔴 غیرفعال"
    text = (
        f"🏷 <b>{cat.name}</b>\n\n"
        f"📊 وضعیت: {status}\n"
    )
    if cat.emoji:
        text += f"🎨 ایموجی: {cat.emoji}\n"
    if cat.description:
        text += f"📝 توضیحات: {cat.description}\n"
    
    toggle_text = "🔴 غیرفعال کردن" if cat.is_active else "🟢 فعال کردن"
    keyboard = [
        [types.InlineKeyboardButton(text=toggle_text, callback_data=f"accat:toggle:{cat.id}")],
        [types.InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"accat:edit:{cat.id}")],
        [types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"accat:delete:{cat.id}")],
        [back_button("accat:list")],
    ]
    
    await safe_edit_text(callback, text, 
                        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data.startswith("accat:toggle:"))
async def cb_accat_toggle(callback: CallbackQuery, uow, user: User) -> None:
    """Toggle category active status."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    cat_id = parts[2]
    cs = CustomService(uow)
    cat = await cs.toggle_category_active(cat_id)
    
    if not cat:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    await uow.commit()
    status = "فعال" if cat.is_active else "غیرفعال"
    await callback.answer(f"✅ دسته {status} شد")
    
    # Refresh view
    await cb_accat_view(callback, uow, user)


@router.callback_query(F.data.startswith("accat:edit:"))
async def cb_accat_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Start editing a category."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    cat_id = parts[2]
    await state.update_data(category_id=cat_id)
    await state.set_state(AdminCustomCategoryStates.waiting_edit_name)
    
    await safe_edit_text(callback,
        "✏️ <b>ویرایش دسته</b>\n\nنام جدید را وارد کنید (یا 'رد' برای رد کردن):",
        reply_markup=single_button_kb(back_button(f"accat:view:{cat_id}")))
    await callback.answer()


@router.message(AdminCustomCategoryStates.waiting_edit_name)
async def collect_edit_name(message: Message, state: FSMContext) -> None:
    """Collect new category name."""
    name = message.text.strip() if message.text else ""
    
    if name.lower() in ["رد", "skip"]:
        data = await state.get_data()
        cat_id = data.get("category_id")
        await state.clear()
        await message.answer("❌ ویرایش لغو شد.", 
                            reply_markup=single_button_kb(back_button(f"accat:view:{cat_id}")))
        return
    
    if not name or len(name) < 2:
        await message.answer("⚠️ نام دسته باید حداقل 2 کاراکتر باشد. دوباره وارد کنید:")
        return
    
    await state.update_data(new_name=name)
    await state.set_state(AdminCustomCategoryStates.waiting_edit_emoji)
    await message.answer(
        "🎨 <b>ایموجی جدید (اختیاری)</b>\n\n"
        "ایموجی جدید را وارد کنید (یا 'رد' برای رد کردن):"
    )


@router.message(AdminCustomCategoryStates.waiting_edit_emoji)
async def collect_edit_emoji(message: Message, state: FSMContext, uow, user: User) -> None:
    """Collect new emoji and save changes."""
    emoji = message.text.strip() if message.text else ""
    
    if emoji.lower() in ["رد", "skip", ""]:
        emoji = None
    elif len(emoji) > 10:
        await message.answer("⚠️ ایموجی خیلی طولانی است. دوباره وارد کنید:")
        return
    
    data = await state.get_data()
    cat_id = data.get("category_id")
    new_name = data.get("new_name")
    
    cs = CustomService(uow)
    try:
        update_data = {"name": new_name}
        if emoji is not None:
            update_data["emoji"] = emoji
        
        cat = await cs.update_category(cat_id, **update_data)
        await uow.commit()
        await state.clear()
        
        await message.answer("✅ <b>دسته با موفقیت ویرایش شد</b>",
                            reply_markup=single_button_kb(back_button(f"accat:view:{cat_id}")))
    except Exception as e:
        logger.exception(f"Failed to update custom category: {e}")
        await state.clear()
        await message.answer(
            f"❌ خطا در ویرایش دسته: {e}",
            reply_markup=single_button_kb(back_button("accat:list"))
        )


@router.callback_query(F.data.startswith("accat:delete:"))
async def cb_accat_delete(callback: CallbackQuery, uow, user: User) -> None:
    """Delete a category."""
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته یافت نشد", show_alert=True)
        return
    
    cat_id = parts[2]
    cs = CustomService(uow)
    
    try:
        success = await cs.delete_category(cat_id)
        await uow.commit()
        
        if success:
            await callback.answer("✅ دسته حذف شد")
            await cb_accat_list(callback, uow, user)
        else:
            await callback.answer("❌ دسته یافت نشد", show_alert=True)
    except Exception as e:
        logger.exception(f"Failed to delete custom category: {e}")
        await callback.answer(f"❌ خطا در حذف دسته: {e}", show_alert=True)
