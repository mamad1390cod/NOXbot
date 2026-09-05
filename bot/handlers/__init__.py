"""Handlers package — **the single composition root** of the router tree.

Router architecture (deliberate, do not spread it around)
---------------------------------------------------------
::

    Dispatcher
    ├── user_router   (Router "user_root")
    │   └── one sub-router per bot/handlers/*.py module
    └── admin_router  (Router "admin_root")
        ├── IsAdmin() gate on message + callback_query
        └── one sub-router per bot/handlers/admin/*.py module,
            each additionally gated by HasPermission(...)

Invariants enforced here
------------------------
1. **One parent per router.** Sub-routers are module-level singletons, so a
   given ``Router`` object can be attached exactly once for the whole process
   lifetime (aiogram raises ``RuntimeError: Router is already attached`` on the
   second attempt). Therefore composition happens *only* in this module.
2. **Composition is idempotent.** ``build_user_router()`` /
   ``build_admin_router()`` cache their result, so importing this package
   twice, calling the builders again from a test, or re-running startup can
   never double-attach or double-apply the permission filters.
3. **No silent duplicates.** A router listed twice (or two aliases of the same
   object) is detected before anything is attached and raises a descriptive
   ``RouterCompositionError`` naming the offender — the error is never
   swallowed.
4. **No forgotten module.** Every ``bot/handlers/**`` module that defines a
   ``router`` must appear in a registry; otherwise startup fails with the list
   of unregistered modules instead of shipping dead buttons.
"""

from __future__ import annotations

import logging
import pkgutil
from importlib import import_module

from aiogram import Router

from bot.handlers import (  # noqa: F401 — imported for handler registration
    account,
    cart,
    configs,
    custom_cart,
    customs,
    menu,
    my_account,
    notify_prefs,
    payments,
    products,
    profile,
    support,
    user_orders,
)
from bot.handlers.admin import ADMIN_ROUTER_SPECS, verify_registry_complete

logger = logging.getLogger(__name__)


class RouterCompositionError(RuntimeError):
    """Raised when the router tree cannot be built safely."""


# --- User side -------------------------------------------------------------- #
# Order matters: more specific routers first, generic/menu fallbacks last.
USER_ROUTER_SPECS: tuple[tuple[str, Router], ...] = (
    ("menu", menu.router),
    ("profile", profile.router),
    ("products", products.router),
    ("configs", configs.router),
    ("cart", cart.router),
    ("customs", customs.router),
    ("custom_cart", custom_cart.router),
    # account.py drives the "account info" FSM (CODM username/email/password)
    # used by account-type products; it was missing from this list, which made
    # the whole account-info purchase flow unreachable.
    ("account", account.router),
    ("support", support.router),
    ("payments", payments.router),
    ("user_orders", user_orders.router),
    ("my_account", my_account.router),
    ("notify_prefs", notify_prefs.router),
)


def _verify_user_registry_complete() -> list[str]:
    """Return bot/handlers/*.py modules with a ``router`` that we never mount."""
    declared = {name for name, _ in USER_ROUTER_SPECS}
    missing: list[str] = []
    for mod_info in pkgutil.iter_modules(__path__):
        name = mod_info.name
        if mod_info.ispkg or name.startswith("_") or name in declared:
            continue
        module = import_module(f"{__name__}.{name}")
        if isinstance(getattr(module, "router", None), Router):
            missing.append(name)
    return missing


def _attach_all(parent: Router, children: list[tuple[str, Router]]) -> None:
    """Attach every child to ``parent`` after proving each one is attachable.

    Two failure modes are reported explicitly (never suppressed):

    * the same ``Router`` object appears twice in ``children`` (duplicate
      registration, or two names bound to one object);
    * the router already has a parent, i.e. something outside this composition
      root attached it first.
    """
    seen: dict[int, str] = {}
    for label, router in children:
        previous = seen.get(id(router))
        if previous is not None:
            raise RouterCompositionError(
                f"Router {router.name!r} is registered twice "
                f"(as {previous!r} and {label!r}). A router object can only be "
                f"attached once — remove the duplicate entry from the registry."
            )
        seen[id(router)] = label

        if router.parent_router is not None:
            raise RouterCompositionError(
                f"Router {router.name!r} (registry entry {label!r}) is already "
                f"attached to {router.parent_router.name!r}. Routers must be "
                f"composed only by bot.handlers (the composition root); check "
                f"for a second include_router() call or a duplicated import path."
            )

    for _, router in children:
        parent.include_router(router)


_user_router: Router | None = None
_admin_router: Router | None = None


def build_user_router() -> Router:
    """Build (once) and return the user-side router tree."""
    global _user_router
    if _user_router is not None:
        return _user_router

    missing = _verify_user_registry_complete()
    if missing:
        raise RouterCompositionError(
            "These bot/handlers modules define a router but are not listed in "
            f"USER_ROUTER_SPECS, so their buttons would never work: {missing}"
        )

    root = Router(name="user_root")
    _attach_all(root, [(name, router) for name, router in USER_ROUTER_SPECS])
    _user_router = root
    logger.debug("user router built with %d sub-routers", len(USER_ROUTER_SPECS))
    return root


def build_admin_router() -> Router:
    """Build (once) and return the admin-side router tree.

    Gating is applied here, exactly once per sub-router:

    * ``IsAdmin()`` on the root — owner or an ACTIVE admin profile;
    * ``HasPermission(...)`` per sub-router — fine-grained RBAC.
    """
    global _admin_router
    if _admin_router is not None:
        return _admin_router

    from bot.filters.admin import HasPermission, IsAdmin

    missing = verify_registry_complete()
    if missing:
        raise RouterCompositionError(
            "These bot/handlers/admin modules define a router but are not "
            f"listed in ADMIN_ROUTER_SPECS, so their buttons would never work: {missing}"
        )

    root = Router(name="admin_root")
    root.message.filter(IsAdmin())
    root.callback_query.filter(IsAdmin())

    children: list[tuple[str, Router]] = [(spec.module, spec.router) for spec in ADMIN_ROUTER_SPECS]
    _attach_all(root, children)  # validates before mutating anything

    for spec in ADMIN_ROUTER_SPECS:
        perms = list(spec.permissions)
        spec.router.message.filter(HasPermission(perms))
        spec.router.callback_query.filter(HasPermission(perms))

    _admin_router = root
    logger.debug("admin router built with %d sub-routers", len(ADMIN_ROUTER_SPECS))
    return root


# Backwards-compatible module-level singletons (main.py imports these).
user_router = build_user_router()
admin_router = build_admin_router()

# Legacy private aliases kept so older call sites keep working; both are now
# idempotent because the builders memoise their result.
_build_user_router = build_user_router
_build_admin_router = build_admin_router

__all__ = [
    "user_router",
    "admin_router",
    "build_user_router",
    "build_admin_router",
    "RouterCompositionError",
    "USER_ROUTER_SPECS",
]
