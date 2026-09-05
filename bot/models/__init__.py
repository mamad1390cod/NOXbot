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