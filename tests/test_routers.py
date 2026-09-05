"""Router composition guarantees (the "Router is already attached" regression).

A module-level ``Router`` object can only ever have one parent. These tests
pin down the invariants that make that impossible to violate accidentally:

* the composition root is idempotent — calling it again returns the same tree;
* every handler module is registered (no dead section);
* a duplicate registry entry fails loudly, with a descriptive error;
* a router that someone else already attached fails loudly too.
"""

from __future__ import annotations

import pytest
from aiogram import Router


def test_builders_are_idempotent():
    from bot.handlers import (
        admin_router,
        build_admin_router,
        build_user_router,
        user_router,
    )

    # Re-running composition must NOT raise "Router is already attached".
    assert build_admin_router() is admin_router
    assert build_admin_router() is admin_router
    assert build_user_router() is user_router


def test_legacy_private_aliases_still_work():
    from bot.handlers import _build_admin_router, _build_user_router, admin_router, user_router

    assert _build_admin_router() is admin_router
    assert _build_user_router() is user_router


def test_every_subrouter_has_exactly_one_parent():
    from bot.handlers import admin_router, user_router

    for root in (user_router, admin_router):
        seen: set[int] = set()
        for sub in root.sub_routers:
            assert sub.parent_router is root, f"{sub.name} is attached to {sub.parent_router}"
            assert id(sub) not in seen, f"{sub.name} appears twice under {root.name}"
            seen.add(id(sub))


def test_admin_registry_covers_every_admin_module():
    from bot.handlers.admin import verify_registry_complete

    assert verify_registry_complete() == []


def test_user_registry_covers_every_handler_module():
    from bot.handlers import _verify_user_registry_complete

    assert _verify_user_registry_complete() == []


def test_duplicate_registration_is_reported_not_silently_ignored():
    from bot.handlers import RouterCompositionError, _attach_all

    parent = Router(name="parent")
    child = Router(name="child")
    with pytest.raises(RouterCompositionError, match="registered twice"):
        _attach_all(parent, [("a", child), ("b", child)])
    # nothing was attached: validation happens before mutation
    assert child.parent_router is None


def test_already_attached_router_is_reported_with_context():
    from bot.handlers import RouterCompositionError, _attach_all

    first_parent = Router(name="first")
    child = Router(name="child")
    first_parent.include_router(child)

    with pytest.raises(RouterCompositionError, match="already attached to 'first'"):
        _attach_all(Router(name="second"), [("child", child)])


def test_admin_subrouters_are_permission_gated():
    from bot.handlers.admin import ADMIN_ROUTER_SPECS

    for spec in ADMIN_ROUTER_SPECS:
        assert spec.permissions, f"{spec.module} has no permission requirement"
        for observer in (spec.router.message, spec.router.callback_query):
            names = [type(f.callback).__name__ for f in observer._handler.filters]
            assert "HasPermission" in names, f"{spec.module} is missing its RBAC gate"
