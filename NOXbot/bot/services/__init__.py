"""Services package for NOXbot Shop.

Layer: Service layer
Each service wraps one or more repositories and exposes business operations.
Services never touch aiogram directly (except NotificationService which sends
messages through the Bot instance).
"""

from bot.services.user import UserService
from bot.services.category import CategoryService
from bot.services.product import ProductService
from bot.services.cart import CartService
from bot.services.order import OrderService
from bot.services.ticket import TicketService
from bot.services.custom import CustomService
from bot.services.custom_cart import CustomCartService
from bot.services.config_shop import ConfigShopService
from bot.services.payment import PaymentService
from bot.services.settings import SettingsService
from bot.services.admin import AdminService
from bot.services.notification import NotificationService
from bot.services.rbac import RbacService, PermissionDenied
from bot.services.settings_registry import REGISTRY, CATEGORIES, CATEGORY_LABELS, spec_for
from bot.services.features import Feature
from bot.services.i18n import TextResolver
from bot.services.financial import FinancialService
from bot.services import reporting
from bot.services.abuse import AntiAbuseService
from bot.services.dashboard import UserDashboardService
from bot.services.broadcast import BroadcastService

__all__ = [
    "UserService",
    "CategoryService",
    "ProductService",
    "CartService",
    "OrderService",
    "TicketService",
    "CustomService",
    "CustomCartService",
    "ConfigShopService",
    "PaymentService",
    "SettingsService",
    "AdminService",
    "NotificationService",
    "RbacService",
    "PermissionDenied",
    "REGISTRY",
    "CATEGORIES",
    "CATEGORY_LABELS",
    "spec_for",
    "Feature",
    "TextResolver",
    "FinancialService",
    "reporting",
    "AntiAbuseService",
    "UserDashboardService",
    "BroadcastService",
]