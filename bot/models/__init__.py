"""Database models package."""

from bot.models.base import Base
from bot.models.user import User
from bot.models.category import Category
from bot.models.product import Product
from bot.models.cart import Cart, CartItem
from bot.models.order import Order, OrderItem, OrderStatus
from bot.models.order_event import OrderStatusEvent
from bot.models.ticket import Ticket, TicketCategory
from bot.models.custom import Custom, CustomCategory, CustomRegistration
from bot.models.config_shop import ConfigProduct, ConfigCategory
from bot.models.payment import Payment
from bot.models.settings import BotSettings
from bot.models.log import AdminLog
from bot.models.rbac import (
    Permission,
    RoleSlug,
    AdminStatus,
    AdminRole,
    AdminProfile,
)
from bot.models.abuse import (
    AbuseType,
    Severity,
    AutoActionType,
    AbuseEvent,
    AutoAction,
)
from bot.models.user_dashboard import (
    TransactionType,
    WishlistItem,
    Transaction,
    Badge,
    Achievement,
)
from bot.models.broadcast import (
    BroadcastStatus,
    MediaType,
    Broadcast,
    BroadcastTemplate,
)

__all__ = [
    "Base",
    "User",
    "Category",
    "Product",
    "Cart",
    "CartItem",
    "Order",
    "OrderItem",
    "OrderStatus",
    "OrderStatusEvent",
    "Ticket",
    "TicketCategory",
    "Custom",
    "CustomCategory",
    "CustomRegistration",
    "ConfigProduct",
    "ConfigCategory",
    "Payment",
    "BotSettings",
    "AdminLog",
    "Permission",
    "RoleSlug",
    "AdminStatus",
    "AdminRole",
    "AdminProfile",
    "AbuseType",
    "Severity",
    "AutoActionType",
    "AbuseEvent",
    "AutoAction",
    "TransactionType",
    "WishlistItem",
    "Transaction",
    "Badge",
    "Achievement",
    "BroadcastStatus",
    "MediaType",
    "Broadcast",
    "BroadcastTemplate",
]

# --------------------------------------------------------------------------- #
#  Auto-registration of model modules living outside this list
# --------------------------------------------------------------------------- #
# Any bot/models/*.py that is not imported above is imported here, so a model
# added later (wallet top-ups, coupons, ...) is always known to the ORM and to
# ``Base.metadata.create_all`` - otherwise its table is never created and every
# query against it fails.
def _autoload_extra_models() -> None:
    import logging
    import pkgutil
    from importlib import import_module

    log = logging.getLogger(__name__)
    for info in pkgutil.iter_modules(__path__):
        if info.ispkg or info.name.startswith("_") or info.name in {"base", "compat"}:
            continue
        module_name = f"{__name__}.{info.name}"
        if module_name in globals().get("_LOADED_MODULES", ()):  # pragma: no cover
            continue
        try:
            import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            log.error("model module %s could not be imported: %s: %s", module_name, type(exc).__name__, exc)


_autoload_extra_models()

# Completes any ``back_populates`` whose counterpart is missing (see the module
# docstring); importing it also registers the before_configured hook.
from bot.models import compat  # noqa: E402,F401
