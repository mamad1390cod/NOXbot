"""Shop section keyboards."""

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import back_button


def products_menu_keyboard(
    categories: Sequence,
    callback_prefix: str = "prod_cat",
) -> InlineKeyboardMarkup:
    """Build keyboard for product categories."""
    keyboard = []
    for cat in categories:
        label = cat.name
        keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{cat.id}")]
        )
    keyboard.append([back_button("menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def products_list_keyboard(
    products: Sequence,
    callback_prefix: str = "prod_sel",
    page: int = 0,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Build keyboard for product list."""
    keyboard = []
    for product in products:
        title = product.title
        if product.discount_percent:
            title = f"{title} ⬇️{product.discount_percent}٪"
        keyboard.append(
            [InlineKeyboardButton(text=title, callback_data=f"{callback_prefix}:{product.id}")]
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page:prod:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:prod:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([back_button("menu:products")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_menu_keyboard(categories: Sequence) -> InlineKeyboardMarkup:
    """Build keyboard for custom tournament categories."""
    keyboard = []
    for cat in categories:
        keyboard.append(
            [InlineKeyboardButton(text=cat.name, callback_data=f"custom_cat:{cat.id}")]
        )
    keyboard.append([back_button("menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def config_menu_keyboard(categories: Sequence) -> InlineKeyboardMarkup:
    """Build keyboard for config product categories."""
    keyboard = []
    for cat in categories:
        keyboard.append(
            [InlineKeyboardButton(text=cat.name, callback_data=f"config_cat:{cat.id}")]
        )
    keyboard.append([back_button("menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)