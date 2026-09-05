"""RBAC keyboards — admin roles & permission management."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button, home_button
from bot.models.rbac import (
    AdminProfile,
    AdminRole,
    AdminStatus,
    Permission,
)
from bot.services.rbac import ROLE_NAMES
from bot.utils.callback_data import cb, permission_codec


def roles_menu_keyboard() -> InlineKeyboardMarkup:
    """Top-level roles & admins menu."""
    keyboard = [
        [InlineKeyboardButton(text="👥 لیست ادمین‌ها", callback_data="admin:roles:list")],
        [InlineKeyboardButton(text="🎭 لیست نقش‌ها", callback_data="admin:roles:roles")],
        [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="admin:roles:add")],
        [back_button("admin:panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_list_keyboard(profiles: Sequence[AdminProfile]) -> InlineKeyboardMarkup:
    """List of admin profiles with their role + status."""
    keyboard = []
    for p in profiles:
        if not p.user:
            continue
        role = p.role.slug if p.role else "بدون نقش"
        status_icon = {
            AdminStatus.ACTIVE: "🟢",
            AdminStatus.DISABLED: "⚪",
            AdminStatus.SUSPENDED: "🔴",
        }.get(p.status, "❔")
        label = f"{status_icon} {p.user.username or p.user.first_name or p.user.telegram_id} ({role})"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=cb("admin:roles:profile", p.user_id))
        ])
    keyboard.append([back_button("admin:roles")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def role_list_keyboard(roles: Sequence[AdminRole]) -> InlineKeyboardMarkup:
    """List of roles for editing permissions."""
    keyboard = []
    for r in roles:
        n = len(r.permission_set())
        label = f"{r.name} ({n} دسترسی)"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=cb("admin:roles:role", r.id))
        ])
    keyboard.append([back_button("admin:roles")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def role_permissions_keyboard(role: AdminRole) -> InlineKeyboardMarkup:
    """Toggle-permission keyboard for a role."""
    perms = role.permission_set()
    keyboard = []
    for perm in Permission:
        check = "✅" if perm in perms else "⬜"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{check} {perm.label}",
                # Permission names are long; a 6-char stable code keeps the
                # payload under Telegram's 64-byte callback_data limit.
                callback_data=cb("admin:roles:perm", role.id, permission_codec().encode(perm.value)),
            )
        ])
    keyboard.append([
        InlineKeyboardButton(text="✅ ذخیره و بازگشت", callback_data="admin:roles:roles")
    ])
    keyboard.append([back_button("admin:roles")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def role_picker_keyboard(roles: Sequence[AdminRole], action: str = "pick") -> InlineKeyboardMarkup:
    """Pick a role for a new/edited admin. ``action`` is the callback suffix."""
    keyboard = []
    for r in roles:
        keyboard.append([
            InlineKeyboardButton(text=r.name, callback_data=cb("admin:roles", action, r.id))
        ])
    keyboard.append([back_button("admin:roles")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_actions_keyboard(profile: AdminProfile) -> InlineKeyboardMarkup:
    """Actions for a single admin profile."""
    user_id = profile.user_id
    role = profile.role.slug if profile.role else "none"
    keyboard = []

    if profile.status == AdminStatus.ACTIVE:
        keyboard.append([
            InlineKeyboardButton(text="⏸ غیرفعال", callback_data=cb("admin:roles:disable", user_id)),
            InlineKeyboardButton(text="🔒 تعلیق", callback_data=cb("admin:roles:suspend", user_id)),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="▶️ فعال", callback_data=cb("admin:roles:enable", user_id)),
        ])

    keyboard.append([
        InlineKeyboardButton(text="🎭 تغییر نقش", callback_data=cb("admin:roles:changerole", user_id)),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🗑 حذف ادمین", callback_data=cb("admin:roles:remove", user_id)),
    ])
    keyboard.append([back_button("admin:roles:list")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)