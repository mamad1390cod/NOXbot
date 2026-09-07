"""Admin handlers package."""

from bot.handlers.admin.admin_panel import router as admin_panel_router
from bot.handlers.admin.admin_products import router as admin_products_router
from bot.handlers.admin.admin_categories import router as admin_categories_router
from bot.handlers.admin.admin_configs import router as admin_configs_router
from bot.handlers.admin.admin_customs import router as admin_customs_router
from bot.handlers.admin.admin_tickets import router as admin_tickets_router
from bot.handlers.admin.admin_payments import router as admin_payments_router
from bot.handlers.admin.admin_users import router as admin_users_router
from bot.handlers.admin.admin_broadcast import router as admin_broadcast_router
from bot.handlers.admin.admin_settings import router as admin_settings_router
from bot.handlers.admin.admin_orders import router as admin_orders_router
from bot.handlers.admin.admin_roles import router as admin_roles_router
from bot.handlers.admin.admin_finance import router as admin_finance_router
from bot.handlers.admin.admin_abuse import router as admin_abuse_router
from bot.handlers.admin.orphans import router as admin_orphans_router
from bot.handlers.admin.admin_ticket_categories import router as admin_ticket_categories_router
from bot.handlers.admin.admin_custom_categories import router as admin_custom_categories_router
from bot.handlers.admin.admin_backup import router as admin_backup_router
from bot.handlers.admin.admin_topup import router as admin_topup_router

__all__ = [
    "admin_panel_router",
    "admin_products_router",
    "admin_categories_router",
    "admin_configs_router",
    "admin_customs_router",
    "admin_tickets_router",
    "admin_payments_router",
    "admin_users_router",
    "admin_broadcast_router",
    "admin_settings_router",
    "admin_orders_router",
    "admin_roles_router",
    "admin_finance_router",
    "admin_abuse_router",
    "admin_orphans_router",
    "admin_topup_router",
    "admin_ticket_categories_router",
    "admin_custom_categories_router",
    "admin_backup_router",
]