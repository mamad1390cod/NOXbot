"""Admin handlers package — **declaration only, no composition**.

Architecture rule (see ``bot/handlers/__init__.py``)
---------------------------------------------------
This package is *not* allowed to attach routers to a parent. It only:

1. imports every admin sub-module (so their handlers get registered on their
   own module-level ``router`` object), and
2. publishes ``ADMIN_ROUTER_SPECS`` — the single source of truth listing every
   admin sub-router together with the permission(s) required to use it.

Attaching is done exactly once, by the composition root in
``bot.handlers.__init__``. Keeping declaration and composition apart is what
prevents the "Router is already attached to <Router 'admin_router'>" class of
bug: a module-level ``Router`` object can only ever have **one** parent, so
there must be exactly **one** place that attaches it.

Adding a new admin module
-------------------------
Create ``bot/handlers/admin/admin_<x>.py`` with a module-level
``router = Router(name="admin_<x>")`` and add one entry to
``ADMIN_ROUTER_SPECS``. ``verify_registry_complete()`` (called at startup)
fails loudly if a module is forgotten, so a new section can never end up with
"dead buttons" because nobody registered its router.
"""

from __future__ import annotations

import pkgutil
from dataclasses import dataclass
from importlib import import_module

from aiogram import Router

from bot.models.rbac import Permission

from bot.handlers.admin.admin_abuse import router as admin_abuse_router
from bot.handlers.admin.admin_broadcast import router as admin_broadcast_router
from bot.handlers.admin.admin_categories import router as admin_categories_router
from bot.handlers.admin.admin_configs import router as admin_configs_router
from bot.handlers.admin.admin_customs import router as admin_customs_router
from bot.handlers.admin.admin_finance import router as admin_finance_router
from bot.handlers.admin.admin_orders import router as admin_orders_router
from bot.handlers.admin.admin_panel import router as admin_panel_router
from bot.handlers.admin.admin_payments import router as admin_payments_router
from bot.handlers.admin.admin_products import router as admin_products_router
from bot.handlers.admin.admin_roles import router as admin_roles_router
from bot.handlers.admin.admin_settings import router as admin_settings_router
from bot.handlers.admin.admin_tickets import router as admin_tickets_router
from bot.handlers.admin.admin_users import router as admin_users_router
from bot.handlers.admin.orphans import router as admin_orphans_router


@dataclass(frozen=True)
class AdminRouterSpec:
    """One admin sub-router and the permissions that unlock it."""

    module: str  # module name inside bot.handlers.admin (for completeness check)
    router: Router
    permissions: tuple[Permission, ...]


ADMIN_ROUTER_SPECS: tuple[AdminRouterSpec, ...] = (
    AdminRouterSpec("admin_panel", admin_panel_router, (Permission.VIEW_DASHBOARD,)),
    AdminRouterSpec(
        "admin_products",
        admin_products_router,
        (Permission.MANAGE_PRODUCTS, Permission.DELETE_PRODUCTS),
    ),
    AdminRouterSpec(
        "admin_categories",
        admin_categories_router,
        (Permission.MANAGE_PRODUCTS, Permission.MANAGE_CONFIGS, Permission.MANAGE_CUSTOMS),
    ),
    AdminRouterSpec(
        "admin_configs",
        admin_configs_router,
        (Permission.MANAGE_CONFIGS, Permission.DELETE_PRODUCTS),
    ),
    AdminRouterSpec("admin_customs", admin_customs_router, (Permission.MANAGE_CUSTOMS,)),
    AdminRouterSpec("admin_tickets", admin_tickets_router, (Permission.MANAGE_TICKETS,)),
    AdminRouterSpec(
        "admin_payments",
        admin_payments_router,
        (Permission.MANAGE_PAYMENTS, Permission.APPROVE_PAYMENTS),
    ),
    AdminRouterSpec("admin_users", admin_users_router, (Permission.MANAGE_USERS,)),
    AdminRouterSpec("admin_broadcast", admin_broadcast_router, (Permission.SEND_BROADCAST,)),
    AdminRouterSpec("admin_settings", admin_settings_router, (Permission.CHANGE_SETTINGS,)),
    AdminRouterSpec(
        "admin_orders",
        admin_orders_router,
        (Permission.MANAGE_PAYMENTS, Permission.DELETE_ORDERS),
    ),
    AdminRouterSpec("admin_roles", admin_roles_router, (Permission.MANAGE_ADMINS,)),
    AdminRouterSpec(
        "admin_finance",
        admin_finance_router,
        (Permission.VIEW_FINANCIAL_REPORTS, Permission.EXPORT_REPORTS),
    ),
    AdminRouterSpec("admin_abuse", admin_abuse_router, (Permission.MANAGE_USERS,)),
    # orphans.py hosts the fallback handlers for buttons whose feature lives in
    # several sections; dashboard permission is the least-privilege choice.
    AdminRouterSpec("orphans", admin_orphans_router, (Permission.VIEW_DASHBOARD,)),
)


def verify_registry_complete() -> list[str]:
    """Return admin modules that expose a ``router`` but are not registered.

    Called by the composition root at startup. An empty list means every admin
    handler module is reachable by users (no silently dead section).
    """
    declared = {spec.module for spec in ADMIN_ROUTER_SPECS}
    missing: list[str] = []
    for mod_info in pkgutil.iter_modules(__path__):
        name = mod_info.name
        if name.startswith("_") or name in declared:
            continue
        module = import_module(f"{__name__}.{name}")
        if isinstance(getattr(module, "router", None), Router):
            missing.append(name)
    return missing


__all__ = [
    "ADMIN_ROUTER_SPECS",
    "AdminRouterSpec",
    "verify_registry_complete",
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
]
