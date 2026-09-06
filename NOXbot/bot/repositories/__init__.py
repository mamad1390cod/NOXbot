"""Repository package."""

from bot.repositories.base import BaseRepository
from bot.repositories.user import UserRepository
from bot.repositories.category import CategoryRepository
from bot.repositories.product import ProductRepository
from bot.repositories.cart import CartRepository
from bot.repositories.order import OrderRepository, OrderDeliveryRepository
from bot.repositories.ticket import TicketRepository, TicketCategoryRepository
from bot.repositories.custom import CustomRepository, CustomCategoryRepository, CustomRegistrationRepository, CustomCartRepository
from bot.repositories.config_shop import ConfigProductRepository
from bot.repositories.payment import PaymentRepository
from bot.repositories.settings import SettingsRepository
from bot.repositories.log import AdminLogRepository
from bot.repositories.rbac import AdminRoleRepository, AdminProfileRepository
from bot.repositories.finance import FinanceRepository
from bot.repositories.abuse import AbuseRepository
from bot.repositories.user_dashboard import (
    WishlistRepository,
    TransactionRepository,
    AchievementRepository,
    BadgeRepository,
)
from bot.repositories.broadcast import BroadcastRepository, BroadcastTemplateRepository
from bot.repositories.topup import TopUpAmountRepository, TopUpReceiptRepository, TopUpRequestRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "CategoryRepository",
    "ProductRepository",
    "CartRepository",
    "OrderRepository",
    "OrderDeliveryRepository",
    "TicketRepository",
    "TicketCategoryRepository",
    "CustomRepository",
    "CustomCategoryRepository",
    "CustomRegistrationRepository",
    "CustomCartRepository",
    "ConfigProductRepository",
    "PaymentRepository",
    "SettingsRepository",
    "AdminLogRepository",
    "AdminRoleRepository",
    "AdminProfileRepository",
    "FinanceRepository",
    "AbuseRepository",
    "WishlistRepository",
    "TransactionRepository",
    "AchievementRepository",
    "BadgeRepository",
    "BroadcastRepository",
    "BroadcastTemplateRepository",
]