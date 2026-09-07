"""RBAC / Permission Tests — Verify authorization correctness."""

import uuid
import json
import pytest
from sqlalchemy import select

from bot.models.user import User, UserRole
from bot.models.rbac import AdminRole, AdminProfile, AdminStatus, Permission, RoleSlug


class TestRBAC:
    """Verify role-based access control."""

    @pytest.mark.asyncio
    async def test_role_permission_set_parsing(self, session):
        """Role.permission_set() must correctly parse JSON permissions."""
        role = AdminRole(
            id=str(uuid.uuid4()),
            name="Test Role",
            slug="test_role",
            permissions=json.dumps([
                Permission.VIEW_DASHBOARD.value,
                Permission.MANAGE_PRODUCTS.value,
            ]),
            is_system=False,
        )
        session.add(role)
        await session.flush()
        
        perms = role.permission_set()
        assert Permission.VIEW_DASHBOARD in perms
        assert Permission.MANAGE_PRODUCTS in perms
        assert Permission.MANAGE_ADMINS not in perms

    @pytest.mark.asyncio
    async def test_empty_permissions(self, session):
        """Role with empty permissions must return empty set."""
        role = AdminRole(
            id=str(uuid.uuid4()),
            name="Empty Role",
            slug="empty_role",
            permissions="[]",
            is_system=False,
        )
        session.add(role)
        await session.flush()
        
        perms = role.permission_set()
        assert len(perms) == 0

    @pytest.mark.asyncio
    async def test_invalid_permissions_ignored(self, session):
        """Invalid permission slugs must be silently ignored."""
        role = AdminRole(
            id=str(uuid.uuid4()),
            name="Mixed Role",
            slug="mixed_role",
            permissions=json.dumps([
                Permission.VIEW_DASHBOARD.value,
                "nonexistent_permission",
                "another_fake",
            ]),
            is_system=False,
        )
        session.add(role)
        await session.flush()
        
        perms = role.permission_set()
        assert Permission.VIEW_DASHBOARD in perms
        assert len(perms) == 1  # Only valid permission

    @pytest.mark.asyncio
    async def test_admin_profile_active_check(self, session, test_user):
        """AdminProfile.is_active must check status correctly."""
        role = AdminRole(
            id=str(uuid.uuid4()),
            name="Active Role",
            slug="active_role",
            permissions="[]",
            is_system=False,
        )
        session.add(role)
        await session.flush()
        
        profile = AdminProfile(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            role_id=role.id,
            status=AdminStatus.ACTIVE,
        )
        session.add(profile)
        await session.flush()
        
        assert profile.is_active is True
        
        profile.status = AdminStatus.DISABLED
        assert profile.is_active is False
        
        profile.status = AdminStatus.SUSPENDED
        assert profile.is_active is False


class TestErrorHandling:
    """Verify error handling patterns in the codebase."""

    def test_no_bare_except_pass(self):
        """No 'except: pass' patterns should exist in critical code."""
        import os
        critical_dirs = ['bot/services', 'bot/handlers']
        
        violations = []
        for d in critical_dirs:
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith('.py'):
                        path = os.path.join(root, f)
                        with open(path, 'r') as fh:
                            lines = fh.readlines()
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if stripped == 'pass' and i > 0:
                                prev = lines[i-1].strip()
                                if prev.startswith('except') and ':' in prev:
                                    # Check it's not 'except SomeError:'
                                    if prev == 'except:' or 'Exception' in prev:
                                        violations.append(f"{path}:{i+1}")
        
        assert len(violations) == 0, (
            f"Found 'except: pass' or 'except Exception: pass' in: {violations}"
        )

    def test_no_hardcoded_secrets(self):
        """No hardcoded bot tokens or passwords in source."""
        import os
        import re
        
        token_pattern = re.compile(r'\d{8,10}:[A-Za-z0-9_-]{35}')
        violations = []
        
        for root, dirs, files in os.walk('bot'):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    path = os.path.join(root, f)
                    with open(path, 'r') as fh:
                        content = fh.read()
                    matches = token_pattern.findall(content)
                    if matches:
                        violations.append(f"{path}: {matches}")
        
        assert len(violations) == 0, f"Hardcoded tokens found: {violations}"
