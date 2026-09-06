"""Admin user management handlers."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin import admin_users_keyboard, user_detail_keyboard
from bot.keyboards.common import back_button, single_button_kb
from bot.models.log import LogAction
from bot.models.user import User, UserRole
from bot.services.admin import AdminService
from bot.services.user import UserService
from bot.states import SearchStates
from bot.utils.format import format_price
from bot.utils.editing import safe_edit_text

router = Router(name="admin_users")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin:users")
async def cb_admin_users(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, "👥 <b>مدیریت کاربران</b>", reply_markup=admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "auser:search")
async def cb_user_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_user_query)
    await callback.message.answer("🔍 آیدی، یوزرنیم یا نام کاربر را وارد کنید:")
    await callback.answer()


@router.message(SearchStates.waiting_user_query)
async def do_user_search(message: Message, state: FSMContext, uow, user: User) -> None:
    query = message.text.strip() if message.text else ""
    us = UserService(uow)
    users = await us.search_users(query, limit=10)
    await state.clear()

    if not users:
        await message.answer("❌ کاربری یافت نشد.")
        return

    keyboard = []
    for u in users:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"👤 {u.username or u.first_name or u.telegram_id}",
                callback_data=f"auser:detail:{u.id}",
            )
        ])
    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("🔍 نتایج جستجو:", reply_markup=kb)


@router.callback_query(F.data == "auser:list")
async def cb_user_list(callback: CallbackQuery, uow, user: User) -> None:
    us = UserService(uow)
    users = await us.get_all_for_admin(limit=20)
    if not users:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:users")]])
        await safe_edit_text(callback, "کاربری یافت نشد.", reply_markup=kb)
        await callback.answer()
        return
    keyboard = []
    for u in users:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"👤 {u.username or u.first_name or u.telegram_id}",
                callback_data=f"auser:detail:{u.id}",
            )
        ])
    keyboard.append([back_button("admin:users")])
    await safe_edit_text(callback, "👥 <b>لیست کاربران</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@router.callback_query(F.data.startswith("auser:detail:"))
async def cb_user_detail(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    us = UserService(uow)
    details = await us.get_user_details(target_id)
    if not details:
        await callback.answer("کاربر یافت نشد", show_alert=True)
        return
    target = details["user"]
    is_banned = target.is_banned
    is_admin = target.role == UserRole.ADMIN

    text = (
        f"👤 <b>مشخصات کاربر</b>\n\n"
        f"🆔 آیدی تلگرام: <code>{target.telegram_id}</code>\n"
        f"👤 نام: {target.first_name or ''} {target.last_name or ''}\n"
        f"👤 یوزرنیم: @{target.username or '-'}\n"
        f"📊 نقش: {target.role.value}\n"
        f"🚫 بن: {'بله' if is_banned else 'خیر'}\n"
        f"💰 کل خرید: {format_price(target.total_spent)} تومان\n"
        f"📅 عضویت: {target.created_at.strftime('%Y-%m-%d') if target.created_at else '—'}\n"
        f"📋 سفارشات: {details['stats']['total_orders']}\n"
        f"💳 پرداخت‌ها: {details['stats']['total_payments']}\n"
        f"🎫 تیکت‌ها: {details['stats']['total_tickets']}\n"
        f"🎮 ثبت‌نام‌ها: {details['stats']['total_registrations']}\n"
    )
    kb = user_detail_keyboard(target.id, is_banned, is_admin)
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("auser:ban:"))
async def cb_user_ban(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    us = UserService(uow)
    await us.ban_user(target_id, reason="ادمین")
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.USER_BAN, target_id=target_id, description="بن کاربر")
    await uow.flush()

    await uow.commit()
    await callback.answer("بن شد")
    await cb_user_detail(callback, uow, user)


@router.callback_query(F.data.startswith("auser:unban:"))
async def cb_user_unban(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    us = UserService(uow)
    await us.unban_user(target_id)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.USER_UNBAN, target_id=target_id, description="رفع بن")
    await uow.flush()

    await uow.commit()
    await callback.answer("رفع بن شد")
    await cb_user_detail(callback, uow, user)


@router.callback_query(F.data.startswith("auser:makeadmin:"))
async def cb_user_make_admin(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    from bot.services.rbac import RbacService
    rbac = RbacService(uow)
    target = await rbac.uow.users.get(target_id)
    if not target:
        await callback.answer("کاربر یافت نشد", show_alert=True)
        return
    if rbac.is_owner(target):
        await callback.answer("مالک همیشه ادمین است", show_alert=True)
        return
    try:
        await rbac.create_admin(target.telegram_id, "moderator", added_by=user)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
                         target_id=target.id, description=f"ترفیع کاربر {target.username or target.id} به ادمین")
    await uow.flush()

    await uow.commit()
    await callback.answer("ادمین شد")
    await cb_user_detail(callback, uow, user)


@router.callback_query(F.data.startswith("auser:removeadmin:"))
async def cb_user_remove_admin(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    from bot.services.rbac import RbacService
    rbac = RbacService(uow)
    target = await rbac.uow.users.get(target_id)
    if rbac.is_owner(target) if target else False:
        await callback.answer("مالک قابل حذف نیست", show_alert=True)
        return
    await rbac.remove_admin(target_id)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
                         target_id=target_id, description="حذف از ادمین")
    await uow.flush()

    await uow.commit()
    await callback.answer("حذف از ادمین")
    await cb_user_detail(callback, uow, user)


@router.callback_query(F.data.startswith("auser:del:"))
async def cb_user_delete(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚠️ تایید حذف", callback_data=f"auser:confirm_del:{target_id}"),
         types.InlineKeyboardButton(text="❌ انصراف", callback_data="admin:users")]
    ])
    await safe_edit_text(callback, "⚠️ آیا از حذف این کاربر مطمئن هستید؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("auser:confirm_del:"))
async def cb_user_confirm_delete(callback: CallbackQuery, uow, user: User) -> None:
    target_id = callback.data.split(":", 2)[2]
    us = UserService(uow)
    await us.uow.users.delete(target_id)
    await uow.flush()

    await uow.commit()
    api = AdminService(uow)
    await api.log_action(user, LogAction.USER_DELETE, target_id=target_id, description="حذف کاربر")
    await uow.flush()

    await uow.commit()
    await safe_edit_text(callback, "✅ کاربر حذف شد.", reply_markup=single_button_kb(back_button("admin:users")))
    await callback.answer()