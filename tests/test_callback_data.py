"""callback_data safety: the ``BUTTON_DATA_INVALID`` regression."""

from __future__ import annotations

import pytest

from bot.utils.callback_data import (
    CALLBACK_DATA_LIMIT,
    ValueCodec,
    cb,
    expand,
    is_token,
    permission_codec,
)


def test_short_payload_is_returned_untouched():
    assert cb("admin", "roles", "list") == "admin:roles:list"


def test_oversized_payload_becomes_a_short_token_that_expands_back():
    uuid_a = "0f5e96f9-42f3-4b69-b3ee-25116ff081f6"
    uuid_b = "26893222-fcf1-4b77-8127-72b62cff1fb0"
    raw = f"aprod:move_to:{uuid_a}:{uuid_b}"
    assert len(raw.encode()) > CALLBACK_DATA_LIMIT

    data = cb("aprod:move_to", uuid_a, uuid_b)
    assert len(data.encode()) <= CALLBACK_DATA_LIMIT
    assert is_token(data)
    assert expand(data) == raw


def test_token_is_stable_for_the_same_payload():
    long_a = cb("x" * 40, "y" * 40)
    long_b = cb("x" * 40, "y" * 40)
    assert long_a == long_b


def test_unknown_token_expands_to_none():
    assert expand("ct:deadbeefdeadbeef") is None


def test_value_codec_round_trip():
    codec = ValueCodec(["view_dashboard", "manage_products", "export_reports"])
    for value in ("view_dashboard", "manage_products", "export_reports"):
        assert codec.decode(codec.encode(value)) == value


def test_every_permission_code_round_trips_and_fits():
    from bot.models.rbac import Permission

    codec = permission_codec()
    role_id = "0f5e96f9-42f3-4b69-b3ee-25116ff081f6"
    for perm in Permission:
        code = codec.encode(perm.value)
        assert codec.decode(code) == perm.value
        payload = f"admin:roles:perm:{role_id}:{code}"
        assert len(payload.encode()) <= CALLBACK_DATA_LIMIT, payload


@pytest.mark.asyncio
async def test_real_keyboards_never_exceed_the_limit(seeded):
    """Build the keyboards that used to break, with real database rows."""
    from bot.database.uow import UnitOfWork
    from bot.keyboards.rbac import (
        admin_actions_keyboard,
        admin_list_keyboard,
        role_list_keyboard,
        role_permissions_keyboard,
        role_picker_keyboard,
    )

    from bot.services.rbac import RbacService

    async with UnitOfWork() as uow:
        rbac = RbacService(uow)
        roles = await rbac.list_roles()
        profiles = await rbac.list_admins(limit=10)
        keyboards = [
            role_list_keyboard(roles),
            role_permissions_keyboard(roles[0]),
            role_picker_keyboard(roles, "addrole"),
            admin_list_keyboard(profiles),
        ]
        for profile in profiles:
            keyboards.append(admin_actions_keyboard(profile))

    for markup in keyboards:
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data:
                    assert len(button.callback_data.encode()) <= CALLBACK_DATA_LIMIT, button.callback_data
