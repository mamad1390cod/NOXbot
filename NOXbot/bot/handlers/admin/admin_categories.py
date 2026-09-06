"""Admin category management handlers."""

import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import category_detail_keyboard, category_list_keyboard, category_management_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.user import User
from bot.services.admin import AdminService
from bot.services.category import CategoryService
from bot.states import CategoryStates

router = Router(name="admin_categories")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:categories")
async def cb_admin_categories(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🏷 <b>مدیریت دسته‌بندی‌ها</b>",
        reply_markup=category_management_keyboard("acat"),
    )
    await callback.answer()


# --- Create category ---
@router.callback_query(F.data == "acat:add")
async def cb_category_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    # Ask which type of category
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🛠 دسته محصول", callback_data="acat:add_type:product")],
        [types.InlineKeyboardButton(text="⚡ دسته کانفیگ", callback_data="acat:add_type:config")],
        [types.InlineKeyboardButton(text="🎮 دسته کاستوم", callback_data="accat:list")],
        [back_button("admin:categories")],
    ])
    await safe_edit_text(callback, "🏷 نوع دسته‌بندی را انتخاب کنید:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("acat:add_type:"))
async def cb_category_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("نوع دسته‌بندی نامعتبر", show_alert=True)
        return
    cat_type = parts[2]
    await state.update_data(cat_type=cat_type)
    await state.set_state(CategoryStates.waiting_name)
    await callback.message.answer(f"🏷 نام دسته‌بندی ({cat_type}) را ارسال کنید:")
    await callback.answer()


@router.message(CategoryStates.waiting_name)
async def collect_category_name(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text or not message.text.strip():
        await message.answer("⚠️ نام خالی است:")
        return
    data = await state.get_data()
    cat_type = data.get("cat_type", "product")
    cs = CategoryService(uow)
    cat = await cs.create_category(name=message.text.strip(), type=cat_type)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.CATEGORY_CREATE, target_id=cat.id, description=f"ایجاد دسته {cat.name}")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ دسته‌بندی ایجاد شد.", reply_markup=single_button_kb(back_button("admin:categories")))


# --- List categories ---
@router.callback_query(F.data == "acat:list")
async def cb_category_list(callback: CallbackQuery, uow, user: User) -> None:
    cs = CategoryService(uow)
    cats = await cs.get_all_for_admin("product", limit=100)
    cats += await cs.get_all_for_admin("config", limit=100)
    if not cats:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:categories")]])
        await safe_edit_text(callback, "🏷 دسته‌بندی‌ای ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, 
        "🏷 <b>دسته‌بندی‌ها</b>",
        reply_markup=category_list_keyboard(cats, "acat"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acat:view:"))
async def cb_category_view(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    await safe_edit_text(callback, "🏷 عملیات دسته:", reply_markup=category_detail_keyboard(cat_id, "acat"))
    await callback.answer()


@router.callback_query(F.data.startswith("acat:edit:"))
async def cb_category_edit(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    await state.set_data({"edit_cat_id": cat_id})
    await state.set_state(CategoryStates.waiting_edit_name)
    await callback.message.answer("✏️ نام جدید دسته‌بندی را ارسال کنید:")
    await callback.answer()


@router.message(CategoryStates.waiting_edit_name)
async def do_category_edit_name(message: Message, state: FSMContext, uow, user: User) -> None:
    if not message.text or not message.text.strip():
        await message.answer("⚠️ نام خالی است:")
        return
    data = await state.get_data()
    cat_id = data.get("edit_cat_id")
    if not cat_id:
        await state.clear()
        return
    cs = CategoryService(uow)
    await cs.update_category(cat_id, name=message.text.strip())
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    from bot.models.log import LogAction
    await api.log_action(user, LogAction.CATEGORY_EDIT, target_id=cat_id, description=f"ویرایش دسته به {message.text.strip()}")
    await uow.flush()

    await uow.commit()
    await state.clear()
    await message.answer("✅ دسته‌بندی ویرایش شد.", reply_markup=single_button_kb(back_button("acat:list")))


@router.callback_query(F.data.startswith("acat:vis:"))
async def cb_category_visibility(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    await CategoryService(uow).toggle_visibility(cat_id)
    await uow.flush()

    await uow.commit()
    await callback.answer("تغییر کرد")


@router.callback_query(F.data.startswith("acat:toggle:"))
async def cb_category_toggle(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    await CategoryService(uow).toggle_active(cat_id)
    await uow.flush()

    await uow.commit()
    await callback.answer("تغییر کرد")


@router.callback_query(F.data.startswith("acat:del:"))
async def cb_category_delete(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚠️ تایید حذف", callback_data=f"acat:confirm_del:{cat_id}"),
         types.InlineKeyboardButton(text="❌ انصراف", callback_data="admin:categories")]
    ])
    await safe_edit_text(callback, "⚠️ حذف این دسته تمام آیتم‌های آن را حذف می‌کند. مطمئن هستید؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("acat:confirm_del:"))
async def cb_confirm_category_delete(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("دسته‌بندی یافت نشد", show_alert=True)
        return
    cat_id = parts[2]
    await CategoryService(uow).delete_category(cat_id)
    await uow.flush()

    await uow.commit()
    await safe_edit_text(callback, "✅ دسته حذف شد.", reply_markup=single_button_kb(back_button("admin:categories")))
    await callback.answer()