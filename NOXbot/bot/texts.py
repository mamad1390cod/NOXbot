"""Dynamic text accessors for the shop bot.

Each "constant" is now a function that resolves the current value from the
DB-backed settings store (via the sync ``text_store`` mirror). Handlers keep
their ``from bot.texts import X`` import syntax, but ``X`` is a zero-arg
callable returning the current value — so edits apply instantly.

Backward compatibility: ``X`` used to be a string. Call sites now use ``X()``.
"""

from bot.services import text_store


# --- General ---
def welcome() -> str:
    return text_store.t("welcome_message")


def main_menu() -> str:
    return text_store.t("main_menu_text")


def back() -> str:
    return text_store.button("btn_back")


def cancel() -> str:
    return text_store.button("btn_cancel")


def confirm() -> str:
    return text_store.button("btn_confirm")


def home() -> str:
    return text_store.button("btn_home")


# --- Product ---
def product_not_found() -> str:
    return text_store.t("msg_product_not_found")


def product_out_of_stock() -> str:
    return text_store.t("msg_product_out_of_stock")


def product_invalid() -> str:
    return text_store.t("msg_product_not_found")


# --- Cart ---
def cart_empty() -> str:
    return text_store.t("msg_cart_empty")


def cart_added() -> str:
    return text_store.t("msg_cart_added")


def cart_item_removed() -> str:
    return text_store.t("msg_cart_removed")


def cart_cleared() -> str:
    return text_store.t("msg_cart_cleared")


def cart_qty_updated() -> str:
    return text_store.t("msg_cart_cleared")


# --- Custom ---
def custom_not_found() -> str:
    return text_store.t("msg_custom_registered")


def custom_full() -> str:
    return text_store.t("msg_custom_full")


def custom_already_registered() -> str:
    return text_store.t("msg_custom_already")


def custom_registered() -> str:
    return text_store.t("msg_custom_registered")


# --- Ticket ---
def ticket_created() -> str:
    return text_store.t("msg_ticket_created")


def ticket_closed() -> str:
    return text_store.t("msg_ticket_closed")


def ticket_not_found() -> str:
    return text_store.t("msg_ticket_not_found")


# --- Payment ---
def payment_approved() -> str:
    return text_store.t("payment_approved_message")


def payment_rejected() -> str:
    return text_store.t("payment_rejected_message")


# --- Winner ---
def congratulations() -> str:
    return text_store.t("msg_winner_congratulations")


def tournament_ended() -> str:
    return text_store.t("msg_tournament_ended")


# Backward-compatible aliases so old ``from bot.texts import WELCOME`` code
# that treats them as strings still gets a usable default.
WELCOME = welcome
MAIN_MENU = main_menu
BACK = back
CANCEL = cancel
CONFIRM = confirm
HOME = home
PRODUCT_NOT_FOUND = product_not_found
PRODUCT_OUT_OF_STOCK = product_out_of_stock
PRODUCT_INVALID = product_invalid
CART_EMPTY = cart_empty
CART_ADDED = cart_added
CART_ITEM_REMOVED = cart_item_removed
CART_CLEARED = cart_cleared
CART_QTY_UPDATED = cart_qty_updated
CUSTOM_NOT_FOUND = custom_not_found
CUSTOM_FULL = custom_full
CUSTOM_ALREADY_REGISTERED = custom_already_registered
CUSTOM_REGISTERED = custom_registered
TICKET_CREATED = ticket_created
TICKET_CLOSED = ticket_closed
TICKET_NOT_FOUND = ticket_not_found
PAYMENT_APPROVED = payment_approved
PAYMENT_REJECTED = payment_rejected
CONGRATULATIONS = congratulations
TOURNAMENT_ENDED = tournament_ended