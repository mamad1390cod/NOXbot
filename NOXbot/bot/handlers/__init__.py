"""Handlers package.

Composes user and admin routers. Admin routers are grouped together and gated
by an admin check (handled in the admin_panel router via a global filter).
"""

from bot.handlers import customer_info
from aiogram import Router

from bot.handlers import menu, products, configs, customs, cart, custom_cart, support, payments, profile, user_orders, my_account, notify_prefs, topup  # noqa: F401
from bot.handlers.admin import (
    admin_panel_router,
    admin_products_router,
    admin_categories_router,
    admin_configs_router,
    admin_customs_router,
    admin_tickets_router,
    admin_payments_router,
    admin_ticket_categories_router,
    admin_custom_categories_router,
    admin_backup_router,
    admin_users_router,
    admin_broadcast_router,
    admin_settings_router,
    admin_orders_router,
    admin_roles_router,
    admin_finance_router,
    admin_abuse_router,
    admin_orphans_router,
    admin_topup_router,
)  # noqa: F401

user_router = Router(name="user")
admin_router = Router(name="admin")


def _build_user_router() -> Router:
    r = Router(name="user_router")
    for sub in (
        menu.router,
        profile.router,
        products.router,
        customer_info.router,
        configs.router,
        cart.router,
        customs.router,
        custom_cart.router,
        support.router,
        payments.router,
        user_orders.router,
        my_account.router,
        notify_prefs.router,
        topup.router,
    ):
        r.include_router(sub)
    return r


def _build_admin_router() -> Router:
    r = Router(name="admin_router")
    # Coarse gate: every admin message/callback requires an admin account
    # (owner OR an ACTIVE AdminProfile). This replaces the old owner-only check.
    from bot.filters.admin import IsAdmin, HasPermission
    from bot.models.rbac import Permission
    r.message.filter(IsAdmin())
    r.callback_query.filter(IsAdmin())

    # Fine-grained RBAC: each sub-router requires its permission.
    # Each sub-router's message+callback observers get the permission filter.
    def _gate(sub_router, perms):
        sub_router.message.filter(HasPermission(perms))
        sub_router.callback_query.filter(HasPermission(perms))

    # admin_panel (dashboard/logs/stats) -> VIEW_DASHBOARD
    _gate(admin_panel_router, Permission.VIEW_DASHBOARD)
    _gate(admin_products_router, [Permission.MANAGE_PRODUCTS, Permission.DELETE_PRODUCTS])
    _gate(admin_categories_router, [Permission.MANAGE_PRODUCTS, Permission.MANAGE_CONFIGS, Permission.MANAGE_CUSTOMS])
    _gate(admin_configs_router, [Permission.MANAGE_CONFIGS, Permission.DELETE_PRODUCTS])
    _gate(admin_customs_router, Permission.MANAGE_CUSTOMS)
    _gate(admin_tickets_router, Permission.MANAGE_TICKETS)
    _gate(admin_ticket_categories_router, Permission.MANAGE_TICKETS)
    _gate(admin_payments_router, [Permission.MANAGE_PAYMENTS, Permission.APPROVE_PAYMENTS])
    _gate(admin_users_router, Permission.MANAGE_USERS)
    _gate(admin_broadcast_router, Permission.SEND_BROADCAST)
    _gate(admin_settings_router, Permission.CHANGE_SETTINGS)
    _gate(admin_orders_router, [Permission.MANAGE_PAYMENTS, Permission.DELETE_ORDERS])
    _gate(admin_roles_router, Permission.MANAGE_ADMINS)
    _gate(admin_finance_router, [Permission.VIEW_FINANCIAL_REPORTS, Permission.EXPORT_REPORTS])
    _gate(admin_abuse_router, Permission.MANAGE_USERS)
    _gate(admin_orphans_router, Permission.VIEW_DASHBOARD)
    _gate(admin_topup_router, [Permission.MANAGE_PAYMENTS, Permission.APPROVE_PAYMENTS])
    _gate(admin_backup_router, Permission.MANAGE_PAYMENTS)
    _gate(admin_custom_categories_router, Permission.MANAGE_CUSTOMS)

    for sub in (
        admin_panel_router,
        admin_products_router,
        admin_categories_router,
        admin_configs_router,
        admin_customs_router,
        admin_tickets_router,
        admin_ticket_categories_router,
        admin_custom_categories_router,
        admin_backup_router,
        admin_payments_router,
        admin_users_router,
        admin_broadcast_router,
        admin_settings_router,
        admin_orders_router,
        admin_roles_router,
        admin_finance_router,
        admin_abuse_router,
        admin_orphans_router,
        admin_topup_router,
    ):
        r.include_router(sub)
    return r


user_router = _build_user_router()
admin_router = _build_admin_router()

__all__ = ["user_router", "admin_router"]