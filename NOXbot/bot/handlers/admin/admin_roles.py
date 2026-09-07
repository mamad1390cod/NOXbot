"""Admin roles & permission management handlers."""

import logging

from aiogram import F, Router, types
from bot.utils.editing import safe_edit_text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import back_button, single_button_kb
from bot.keyboards.rbac import (
    admin_actions_keyboard,
    admin_list_keyboard,
    role_list_keyboard,
    role_picker_keyboard,
    role_permissions_keyboard,
    roles_menu_keyboard,
)
from bot.models.log import LogAction
from bot.models.rbac import AdminStatus, Permission, RoleSlug
from bot.models.user import User
from bot.services.rbac import RbacService
from bot.states import AdminRolesStates

router = Router(name="admin_roles")
logger = logging.getLogger(__name__)


# --- Menu ---------------------------------------------------------- #
@router.callback_query(F.data == "admin:roles")
async def cb_roles_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, 
        "🛡 <b>مدیریت نقش‌ها و ادمین‌ها</b>\n\nانتخاب گزینه:",
        reply_markup=roles_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:roles:list")
async def cb_admin_list(callback: CallbackQuery, uow, user: User) -> None:
    rbac = RbacService(uow)
    profiles = await rbac.list_admins(limit=50)
    if not profiles:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[back_button("admin:roles")]])
        await safe_edit_text(callback, "👥 هنوز ادمینی ثبت نشده است.", reply_markup=kb)
        await callback.answer()
        return
    await safe_edit_text(callback, 
        "👥 <b>لیست ادمین‌ها</b>",
        reply_markup=admin_list_keyboard(profiles),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:roles:roles")
async def cb_roles_list(callback: CallbackQuery, uow, user: User) -> None:
    rbac = RbacService(uow)
    roles = await rbac.list_roles()
    await safe_edit_text(callback, 
        "🎭 <b>نقش‌ها</b>\nبرای ویرایش دسترسی‌ها روی نقش بزنید:",
        reply_markup=role_list_keyboard(roles),
    )
    await callback.answer()


# --- Role permission editing ------------------------------------------- #
@router.callback_query(F.data.startswith("admin:roles:role:"))
async def cb_role_permissions(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("نقش یافت نشد", show_alert=True)
        return
    role_id = parts[3]
    rbac = RbacService(uow)
    role = await rbac.get_role(role_id)
    if not role:
        await callback.answer("نقش یافت نشد", show_alert=True)
        return
    await safe_edit_text(callback, 
        f"🎭 <b>دسترسی‌های نقش {role.name}</b>\nبرای تغییر روی هر مورد بزنید:",
        reply_markup=role_permissions_keyboard(role),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rp:"))
async def cb_toggle_perm(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":")
    # rp:<role_id>:<perm_index>
    if len(parts) < 3:
        await callback.answer("دسترسی نامعتبر", show_alert=True)
        return
    role_id = parts[1]
    try:
        perm_index = int(parts[2])
        perm = list(Permission)[perm_index]
    except (ValueError, IndexError):
        await callback.answer("دسترسی نامعتبر", show_alert=True)
        return

    rbac = RbacService(uow)
    role = await rbac.get_role(role_id)
    if not role:
        await callback.answer("نقش یافت نشد", show_alert=True)
        return
    if role.is_system and role.slug == "owner":
        await callback.answer("نقش مالک قابل تغییر نیست", show_alert=True)
        return

    old = role.permissions
    updated = await rbac.toggle_role_permission(role_id, perm)
    await uow.flush()

    await uow.commit()

    await rbac.log_admin_action(
        user, LogAction.SETTINGS_CHANGE, target_type="role", target_id=role_id,
        description=f"تغییر دسترسی {perm.label} برای نقش {role.name}",
        old_data=old, new_data=updated.permissions if updated else None,
    )
    await uow.flush()

    await uow.commit()

    await safe_edit_text(callback, 
        f"🎭 <b>دسترسی‌های نقش {updated.name if updated else role.name}</b>\nبرای هر دسترسی بزنید:",
        reply_markup=role_permissions_keyboard(updated or role),
    )
    await callback.answer()


# --- Add admin --------------------------------------------------------- #
@router.callback_query(F.data == "admin:roles:add")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminRolesStates.waiting_admin_telegram_id)
    await callback.message.answer("➕ آیدی عددی تلگرام کاربری که می‌خواهید ادمین شود را ارسال کنید:")
    await callback.answer()


@router.message(AdminRolesStates.waiting_admin_telegram_id)
async def do_add_admin_telegram(message: Message, state: FSMContext, uow, user: User) -> None:
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit():
        await message.answer("⚠️ آیدی عددی معتبر ارسال کنید:")
        return
    telegram_id = int(raw)
    rbac = RbacService(uow)
    target = await rbac.uow.users.get_by_telegram_id(telegram_id)
    if not target:
        await message.answer("❌ کاربری با این آیدی در سیستم یافت نشد.")
        await state.clear()
        return
    if rbac.is_owner(target):
        await message.answer("⚠️ مالک همیشه ادمین است.")
        await state.clear()
        return
    existing = await rbac.uow.admin_profiles.get_by_user_id(target.id)
    if existing:
        await message.answer("⚠️ این کاربر از قبل ادمین است.")
        await state.clear()
        return

    await state.set_data({"new_admin_user_id": target.id})
    # Show all roles except owner (owner can't be assigned)
    all_roles = await rbac.list_roles(include_system=True)
    roles = [r for r in all_roles if r.slug != "owner"]
    await state.set_state(AdminRolesStates.waiting_role_pick)
    await message.answer(
        f"👤 <b>{target.display_name}</b> را با چه نقشی ادمین کنم؟",
        reply_markup=role_picker_keyboard(roles, "addrole"),
    )


@router.callback_query(F.data.startswith("admin:roles:addrole:"))
async def cb_addadmin_role(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("دسترسی نامعتبر", show_alert=True)
        return
    role_id = parts[3]
    data = await state.get_data()
    target_user_id = data.get("new_admin_user_id")
    rbac = RbacService(uow)
    target = await rbac.uow.users.get(target_user_id)
    role = await rbac.get_role(role_id)
    if not target or not role:
        await callback.answer("خطا", show_alert=True)
        await state.clear()
        return

    profile = await rbac.create_admin(target.telegram_id, role.slug, added_by=user)
    await uow.flush()

    await uow.commit()

    await rbac.log_admin_action(
        user, LogAction.SETTINGS_CHANGE, target_type="admin_profile", target_id=profile.id,
        description=f"افزودن ادمین {target.username or target.id} با نقش {role.name}",
    )
    await uow.flush()

    await uow.commit()

    await state.clear()
    await safe_edit_text(callback, 
        f"✅ <b>{target.display_name}</b> با نقش «{role.name}» ادمین شد.",
        reply_markup=single_button_kb(back_button("admin:roles")),
    )
    await callback.answer()


# --- Role change -------------------------------------------------------- #
@router.callback_query(F.data.startswith("rc:"))
async def cb_change_role(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("دسترسی نامعتبر", show_alert=True)
        return
    user_id = parts[1]  # target user's id
    await state.set_data({"target_user_id": user_id})
    from bot.database.uow import UnitOfWork
    uow = UnitOfWork()
    async with uow:
        rbac = RbacService(uow)
        # Show all roles except owner
        all_roles = await rbac.list_roles(include_system=True)
        roles = [r for r in all_roles if r.slug != "owner"]
    await state.set_state(AdminRolesStates.waiting_role_pick)
    await callback.message.answer("🎭 نقش جدید را انتخاب کنید:", reply_markup=role_picker_keyboard(roles, "setrole"))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:roles:setrole:"))
async def cb_set_role(callback: CallbackQuery, state: FSMContext, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("دسترسی نامعتبر", show_alert=True)
        return
    role_id = parts[3]
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    rbac = RbacService(uow)
    role = await rbac.get_role(role_id)
    target = await rbac.uow.users.get(target_user_id)
    if not role or not target:
        await callback.answer("مشکل در یافتن نقش", show_alert=True)
        await state.clear()
        return
    old_profile = await rbac.uow.admin_profiles.get_by_user_id(target_user_id)
    old_role_slug = old_profile.role.slug if old_profile and old_profile.role else None
    await rbac.set_admin_role(target_user_id, role.slug)
    await uow.flush()

    await uow.commit()
    await rbac.log_admin_action(
        user, LogAction.SETTINGS_CHANGE, target_type="admin_profile", target_id=target_user_id,
        description=f"تغییر نقش {target.username} از {old_role_slug} به {role.slug}",
    )
    await uow.flush()

    await uow.commit()
    await state.clear()
    await safe_edit_text(callback, f"✅ نقش به «{role.name}» تغییر کرد.", reply_markup=single_button_kb(back_button("admin:roles")))
    await callback.answer()


# --- Profile actions --------------------------------------------------- #
@router.callback_query(F.data.startswith("admin:roles:profile:"))
async def cb_profile_detail(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    user_id = parts[3]
    rbac = RbacService(uow)
    profile = await rbac.uow.admin_profiles.get_by_user_id(user_id)
    if not profile:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    from bot.models.rbac import AdminStatus
    status_map = {AdminStatus.ACTIVE: "🟢 فعال", AdminStatus.DISABLED: "⚪ غیرفعال", AdminStatus.SUSPENDED: "🔴 تعلیق"}
    role_name = profile.role.name if profile.role else "بدون نقش"
    text = (
        "🛡 <b>پروفایل ادمین</b>\n\n"
        f"👤 نام: {profile.user.display_name if profile.user else '?'} (@{profile.user.username or '-'})\n"
        f"🎭 نقش: {role_name}\n"
        f"📊 وضعیت: {status_map.get(profile.status, profile.status)}\n"
    )
    if profile.suspended_reason:
        text += f"📝 دلیل تعلیق: {profile.suspended_reason}\n"
    text += f"📅 افزوده‌شده: {profile.added_at.strftime('%Y-%m-%d') if profile.added_at else '—'}\n"
    if profile.last_login_at:
        text += f"🕒 آخرین ورود: {profile.last_login_at.strftime('%Y-%m-%d %H:%M')}\n"
    await safe_edit_text(callback, text, reply_markup=admin_actions_keyboard(profile))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:roles:enable:"))
async def cb_enable(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    user_id = parts[3]
    rbac = RbacService(uow)
    await rbac.set_admin_status(user_id, AdminStatus.ACTIVE)
    await uow.flush()

    await uow.commit()
    await rbac.log_admin_action(user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
                                target_id=user_id, description="فعال‌سازی ادمین")
    await uow.flush()

    await uow.commit()
    await cb_profile_detail(callback, uow, user)


@router.callback_query(F.data.startswith("admin:roles:disable:"))
async def cb_disable(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    user_id = parts[3]
    rbac = RbacService(uow)
    await rbac.set_admin_status(user_id, AdminStatus.DISABLED)
    await uow.flush()

    await uow.commit()
    await rbac.log_admin_action(user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
                                target_id=user_id, description="غیرفعال‌سازی ادمین")
    await uow.flush()

    await uow.commit()
    await cb_profile_detail(callback, uow, user)


@router.callback_query(F.data.startswith("admin:roles:suspend:"))
async def cb_suspend(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    user_id = parts[3]
    await state.set_data({"target_user_id": user_id})
    await state.set_state(AdminRolesStates.waiting_suspend_reason)
    await callback.message.answer("🔒 دلیل تعلیق این ادمین را بنویسید:")
    await callback.answer()


@router.message(AdminRolesStates.waiting_suspend_reason)
async def do_suspend(message: Message, state: FSMContext, uow, user: User) -> None:
    reason = message.text.strip() if message.text else ""
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    rbac = RbacService(uow)
    target = await rbac.uow.users.get(target_user_id) if target_user_id else None
    if target and rbac.is_owner(target):
        await message.answer("⚠️ مالک را نمی‌توان تعلیق کرد.")
        await state.clear()
        return
    await rbac.set_admin_status(target_user_id, AdminStatus.SUSPENDED, reason)
    await uow.flush()

    await uow.commit()
    await rbac.log_admin_action(
        user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
        target_id=target_user_id, description=f"تعلیق ادمین — دلیل: {reason}",
    )
    await uow.flush()

    await uow.commit()
    from bot.keyboards.rbac import admin_list_keyboard
    await state.clear()
    await message.answer("🔒 ادمین تعلیق شد.", reply_markup=single_button_kb(back_button("admin:roles")))


@router.callback_query(F.data.startswith("admin:roles:remove:"))
async def cb_remove(callback: CallbackQuery, uow, user: User) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("پروفایل یافت نشد", show_alert=True)
        return
    user_id = parts[3]
    rbac = RbacService(uow)
    target = await rbac.uow.users.get(user_id)
    if rbac.is_owner(target) if target else False:
        await callback.answer("مالک قابل حذف نیست", show_alert=True)
        return
    await rbac.remove_admin(user_id)
    await uow.flush()

    await uow.commit()
    await rbac.log_admin_action(user, LogAction.SETTINGS_CHANGE, target_type="admin_profile",
                                target_id=user_id, description="حذف ادمین")
    await uow.flush()

    await uow.commit()
    await callback.answer("حذف شد")
    await safe_edit_text(callback, "✅ ادمین حذف شد.", reply_markup=single_button_kb(back_button("admin:roles")))