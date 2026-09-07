"""Keyboard builders for the shop bot."""

from bot.keyboards.common import (
    back_button,
    cancel_button,
    confirm_button,
    home_button,
    main_menu_keyboard,
    pagination_keyboard,
    back_to_menu_keyboard,
)
from bot.keyboards.shop import (
    products_menu_keyboard,
    custom_menu_keyboard,
    config_menu_keyboard,
)
from bot.keyboards.cart_keyboard import (
    cart_keyboard,
    cart_item_keyboard,
)
from bot.keyboards.ticket import (
    ticket_menu_keyboard,
    ticket_categories_keyboard,
    ticket_detail_keyboard,
)
from bot.keyboards.custom_keyboard import (
    custom_panel_keyboard,
    custom_detail_keyboard,
    custom_registration_keyboard,
)

__all__ = [
    "back_button",
    "cancel_button",
    "confirm_button",
    "home_button",
    "main_menu_keyboard",
    "pagination_keyboard",
    "back_to_menu_keyboard",
    "products_menu_keyboard",
    "custom_menu_keyboard",
    "config_menu_keyboard",
    "cart_keyboard",
    "cart_item_keyboard",
    "ticket_menu_keyboard",
    "ticket_categories_keyboard",
    "ticket_detail_keyboard",
    "custom_panel_keyboard",
    "custom_detail_keyboard",
    "custom_registration_keyboard",
]