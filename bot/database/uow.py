"""Unit of Work pattern implementation."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.session import get_session_factory
from bot.repositories import (
    UserRepository,
    CategoryRepository,
    ProductRepository,
    CartRepository,
    OrderRepository,
    TicketRepository,
    TicketCategoryRepository,
    CustomRepository,
    CustomCategoryRepository,
    CustomRegistrationRepository,
    CustomCartRepository,
    ConfigProductRepository,
    PaymentRepository,
    SettingsRepository,
    AdminLogRepository,
    AdminRoleRepository,
    AdminProfileRepository,
    FinanceRepository,
    AbuseRepository,
    WishlistRepository,
    TransactionRepository,
    AchievementRepository,
    BadgeRepository,
    BroadcastRepository,
    BroadcastTemplateRepository,
)


class UnitOfWork:
    """Unit of Work for managing database transactions and repositories."""

    def __init__(self) -> None:
        self._session: Optional[AsyncSession] = None
        self._session_factory = get_session_factory()

        # Repositories (lazy initialization)
        self._users: Optional[UserRepository] = None
        self._categories: Optional[CategoryRepository] = None
        self._products: Optional[ProductRepository] = None
        self._carts: Optional[CartRepository] = None
        self._orders: Optional[OrderRepository] = None
        self._tickets: Optional[TicketRepository] = None
        self._ticket_categories: Optional[TicketCategoryRepository] = None
        self._customs: Optional[CustomRepository] = None
        self._custom_categories: Optional[CustomCategoryRepository] = None
        self._custom_registrations: Optional[CustomRegistrationRepository] = None
        self._custom_carts: Optional[CustomCartRepository] = None
        self._config_products: Optional[ConfigProductRepository] = None
        self._payments: Optional[PaymentRepository] = None
        self._settings: Optional[SettingsRepository] = None
        self._admin_logs: Optional[AdminLogRepository] = None
        self._admin_roles: Optional[AdminRoleRepository] = None
        self._admin_profiles: Optional[AdminProfileRepository] = None
        self._finance: Optional[FinanceRepository] = None
        self._abuse: Optional[AbuseRepository] = None
        self._wishlist: Optional[WishlistRepository] = None
        self._transactions: Optional[TransactionRepository] = None
        self._achievements: Optional[AchievementRepository] = None
        self._badges: Optional[BadgeRepository] = None
        self._broadcasts: Optional[BroadcastRepository] = None
        self._broadcast_templates: Optional[BroadcastTemplateRepository] = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self._session.close()
        self._session = None

    @property
    def session(self) -> AsyncSession:
        """Get current session."""
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use async with UnitOfWork() as uow:")
        return self._session

    @property
    def users(self) -> UserRepository:
        if self._users is None:
            self._users = UserRepository(self.session)
        return self._users

    @property
    def categories(self) -> CategoryRepository:
        if self._categories is None:
            self._categories = CategoryRepository(self.session)
        return self._categories

    @property
    def products(self) -> ProductRepository:
        if self._products is None:
            self._products = ProductRepository(self.session)
        return self._products

    @property
    def carts(self) -> CartRepository:
        if self._carts is None:
            self._carts = CartRepository(self.session)
        return self._carts

    @property
    def orders(self) -> OrderRepository:
        if self._orders is None:
            self._orders = OrderRepository(self.session)
        return self._orders

    @property
    def tickets(self) -> TicketRepository:
        if self._tickets is None:
            self._tickets = TicketRepository(self.session)
        return self._tickets

    @property
    def ticket_categories(self) -> TicketCategoryRepository:
        if self._ticket_categories is None:
            self._ticket_categories = TicketCategoryRepository(self.session)
        return self._ticket_categories

    @property
    def customs(self) -> CustomRepository:
        if self._customs is None:
            self._customs = CustomRepository(self.session)
        return self._customs

    @property
    def custom_categories(self) -> CustomCategoryRepository:
        if self._custom_categories is None:
            self._custom_categories = CustomCategoryRepository(self.session)
        return self._custom_categories

    @property
    def custom_registrations(self) -> CustomRegistrationRepository:
        if self._custom_registrations is None:
            self._custom_registrations = CustomRegistrationRepository(self.session)
        return self._custom_registrations

    @property
    def config_products(self) -> ConfigProductRepository:
        if self._config_products is None:
            self._config_products = ConfigProductRepository(self.session)
        return self._config_products

    @property
    def payments(self) -> PaymentRepository:
        if self._payments is None:
            self._payments = PaymentRepository(self.session)
        return self._payments

    @property
    def settings(self) -> SettingsRepository:
        if self._settings is None:
            self._settings = SettingsRepository(self.session)
        return self._settings

    @property
    def admin_logs(self) -> AdminLogRepository:
        if self._admin_logs is None:
            self._admin_logs = AdminLogRepository(self.session)
        return self._admin_logs

    @property
    def broadcasts(self) -> BroadcastRepository:
        if self._broadcasts is None:
            self._broadcasts = BroadcastRepository(self.session)
        return self._broadcasts

    @property
    def broadcast_templates(self) -> BroadcastTemplateRepository:
        if self._broadcast_templates is None:
            self._broadcast_templates = BroadcastTemplateRepository(self.session)
        return self._broadcast_templates

    @property
    def wishlist(self) -> WishlistRepository:
        if self._wishlist is None:
            self._wishlist = WishlistRepository(self.session)
        return self._wishlist

    @property
    def transactions(self) -> TransactionRepository:
        if self._transactions is None:
            self._transactions = TransactionRepository(self.session)
        return self._transactions

    @property
    def achievements(self) -> AchievementRepository:
        if self._achievements is None:
            self._achievements = AchievementRepository(self.session)
        return self._achievements

    @property
    def badges(self) -> BadgeRepository:
        if self._badges is None:
            self._badges = BadgeRepository(self.session)
        return self._badges

    @property
    def abuse(self) -> AbuseRepository:
        if self._abuse is None:
            self._abuse = AbuseRepository(self.session)
        return self._abuse

    @property
    def custom_carts(self) -> CustomCartRepository:
        if self._custom_carts is None:
            self._custom_carts = CustomCartRepository(self.session)
        return self._custom_carts

    @property
    def finance(self) -> FinanceRepository:
        if self._finance is None:
            self._finance = FinanceRepository(self.session)
        return self._finance

    @property
    def admin_roles(self) -> AdminRoleRepository:
        if self._admin_roles is None:
            self._admin_roles = AdminRoleRepository(self.session)
        return self._admin_roles

    @property
    def admin_profiles(self) -> AdminProfileRepository:
        if self._admin_profiles is None:
            self._admin_profiles = AdminProfileRepository(self.session)
        return self._admin_profiles

    async def commit(self) -> None:
        """Commit transaction."""
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        """Rollback transaction."""
        if self._session:
            await self._session.rollback()

    async def flush(self) -> None:
        """Flush pending changes."""
        if self._session:
            await self._session.flush()


@asynccontextmanager
async def unit_of_work() -> AsyncGenerator[UnitOfWork, None]:
    """Context manager for Unit of Work."""
    uow = UnitOfWork()
    async with uow:
        yield uow