"""Common inline keyboards — labels/emojis driven by the dynamic settings."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services import text_store
from bot.services.features import Feature


def _btn(key: str) -> str:
    """Resolve a dynamic button label (title + emoji) from settings."""
    return text_store.button(key)


def back_button(callback_data: str = "menu:home") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_btn("btn_back"), callback_data=callback_data)


def cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_btn("btn_cancel"), callback_data="action:cancel")


def confirm_button(callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_btn("btn_confirm"), callback_data=callback_data)


def home_button(callback_data: str = "menu:home") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_btn("btn_home"), callback_data=callback_data)


def single_button_kb(button: InlineKeyboardButton) -> InlineKeyboardMarkup:
    """Wrap a single inline button into a reply_markup keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build the main menu keyboard, feature-gated and settings-driven.

    Buttons whose feature toggle is off are hidden; labels come from settings.
    """
    keyboard = []

    if text_store.feature(Feature.PRODUCTS.value):
        keyboard.append([InlineKeyboardButton(text=_btn("btn_products"), callback_data="menu:products")])
    if text_store.feature(Feature.CUSTOMS.value):
        keyboard.append([InlineKeyboardButton(text=_btn("btn_customs"), callback_data="menu:customs")])
    if text_store.feature(Feature.CONFIGS.value):
        keyboard.append([InlineKeyboardButton(text=_btn("btn_configs"), callback_data="menu:configs")])
    if text_store.feature(Feature.ORDERS.value):
        keyboard.append([
            InlineKeyboardButton(text=_btn("btn_cart"), callback_data="menu:cart"),
            InlineKeyboardButton(text=_btn("btn_custom_cart"), callback_data="menu:custom_cart"),
        ])
        keyboard.append([InlineKeyboardButton(text=_btn("btn_orders"), callback_data="orders:list")])
    if text_store.feature(Feature.SUPPORT.value):
        keyboard.append([InlineKeyboardButton(text=_btn("btn_support"), callback_data="menu:support")])

    if text_store.feature(Feature.WALLET_TOPUP.value):
        keyboard.append([InlineKeyboardButton(text="💰 شارژ حساب", callback_data="tu:menu")])

    keyboard.append([InlineKeyboardButton(text=_btn("btn_account"), callback_data="dash:menu")])

    if is_admin:
        keyboard.append([InlineKeyboardButton(text=_btn("btn_admin"), callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def pagination_keyboard(
    page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    keyboard = []
    prev_label = "➡️"
    next_label = "⬅️"
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text=prev_label, callback_data=f"{callback_prefix}:page:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="action:noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text=next_label, callback_data=f"{callback_prefix}:page:{page + 1}"))
    if row:
        keyboard.append(row)
    keyboard.append([back_button()])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[back_button("menu:home")]]
    )