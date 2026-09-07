"""Dynamic settings admin keyboards — built from the settings registry."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button
from bot.services.settings_registry import (
    CATEGORIES,
    CATEGORY_LABELS,
    SettingSpec,
    MEDIA_KEYS,
    TOGGLE_KEYS,
)


def settings_categories_keyboard() -> InlineKeyboardMarkup:
    """Category-browsing keyboard for the settings editor."""
    keyboard = []
    for cat in CATEGORIES:
        keyboard.append([
            InlineKeyboardButton(
                text=CATEGORY_LABELS.get(cat, cat),
                callback_data=f"aset:cat:{cat}",
            )
        ])
    keyboard.append([back_button("admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def settings_specs_keyboard(specs: Sequence[SettingSpec]) -> InlineKeyboardMarkup:
    """Keyboard listing settings in a category (tap to view/edit)."""
    keyboard = []
    for spec in specs:
        keyboard.append([
            InlineKeyboardButton(
                text=spec.label,
                callback_data=f"aset:view:{spec.key}",
            )
        ])
    keyboard.append([back_button("aset:settings")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def settings_detail_keyboard(spec: SettingSpec) -> InlineKeyboardMarkup:
    """Keyboard for a single setting's actions."""
    keyboard = []
    if spec.value_type in ("string", "integer", "json"):
        keyboard.append([
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"aset:edit:{spec.key}")
        ])
    elif spec.value_type == "media":
        keyboard.append([
            InlineKeyboardButton(text="🖼 ارسال تصویر", callback_data=f"aset:media:{spec.key}")
        ])
    elif spec.value_type == "boolean":
        keyboard.append([
            InlineKeyboardButton(text="🔄 تغییر (فعال/غیرفعال)", callback_data=f"aset:toggle:{spec.key}")
        ])
    keyboard.append([back_button(f"aset:cat:{spec.category}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)