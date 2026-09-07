"""rbac roles and admin profiles

Revision ID: f64d5aee9b54
Revises: bce07f0691f7
Create Date: 2026-08-06 01:26:52.040130

Notes:
- Creates admin_roles and admin_profiles tables.
- Seeds the 11 built-in roles with their default permission sets.
- Backfills an AdminProfile for every existing user with role='admin'
  (granting SUPER_ADMIN so no existing admin loses access).
- Adds admin_logs.session_id for the session audit field.
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f64d5aee9b54'
down_revision: Union[str, Sequence[str], None] = 'bce07f0691f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLES: list[tuple[str, str, bool, list[str], int]] = [
    # (name, slug, is_system, permissions, sort_order)
    ("مالک", "owner", True, [
        "view_dashboard", "view_statistics", "manage_users", "manage_products",
        "manage_configs", "manage_customs", "manage_payments", "approve_payments",
        "reject_payments", "manage_tickets", "send_broadcast", "export_reports",
        "backup_database", "restore_database", "change_settings", "manage_admins",
        "delete_products", "delete_orders", "delete_users", "view_financial_reports",
    ], 0),
    ("ادمین ارشد", "super_admin", True, [
        "view_dashboard", "view_statistics", "manage_users", "manage_products",
        "manage_configs", "manage_customs", "manage_payments", "approve_payments",
        "reject_payments", "manage_tickets", "send_broadcast", "export_reports",
        "backup_database", "restore_database", "change_settings",
        "delete_products", "delete_orders", "delete_users", "view_financial_reports",
    ], 1),
    ("مدیر مالی", "financial_manager", False, [
        "view_dashboard", "view_statistics", "manage_payments", "approve_payments",
        "reject_payments", "view_financial_reports", "export_reports",
        "backup_database", "restore_database",
    ], 2),
    ("مدیر پشتیبانی", "support_manager", False, [
        "view_dashboard", "manage_tickets", "send_broadcast",
    ], 3),
    ("مدیر کاستوم‌ها", "tournament_manager", False, [
        "view_dashboard", "manage_customs", "view_statistics",
    ], 4),
    ("مدیر محصولات", "product_manager", False, [
        "view_dashboard", "manage_products", "manage_configs",
        "delete_products", "view_statistics",
    ], 5),
    ("مدیر محتوا", "content_manager", False, [
        "view_dashboard", "manage_customs", "send_broadcast",
    ], 6),
    ("اپراتور", "operator", False, [
        "view_dashboard", "manage_payments", "approve_payments",
        "reject_payments", "manage_tickets",
    ], 7),
    ("ناظر", "moderator", False, [
        "view_dashboard", "manage_tickets", "manage_users",
    ], 8),
    ("بیننده", "viewer", False, [
        "view_dashboard", "view_statistics", "export_reports",
    ], 9),
    ("توسعه‌دهنده", "developer", False, [
        "view_dashboard", "view_statistics", "export_reports",
        "backup_database", "restore_database", "change_settings",
    ], 10),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'admin_roles',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('permissions', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_admin_roles_slug'), 'admin_roles', ['slug'], unique=True)

    op.create_table(
        'admin_profiles',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('suspended_reason', sa.Text(), nullable=True),
        sa.Column('added_by_id', sa.String(), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['added_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['role_id'], ['admin_roles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_admin_profiles_role_id'), 'admin_profiles', ['role_id'], unique=False)
    op.create_index(op.f('ix_admin_profiles_status'), 'admin_profiles', ['status'], unique=False)
    op.create_index(op.f('ix_admin_profiles_user_id'), 'admin_profiles', ['user_id'], unique=True)

    op.add_column('admin_logs', sa.Column('session_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_admin_logs_session_id'), 'admin_logs', ['session_id'], unique=False)

    # --- Seed roles -------------------------------------------------------- #
    conn = op.get_bind()
    import uuid
    for name, slug, is_system, perms, sort in ROLES:
        conn.execute(
            sa.text(
                "INSERT INTO admin_roles "
                "(id, name, slug, description, is_system, permissions, sort_order, created_at, updated_at) "
                "VALUES (:id, :name, :slug, NULL, :is_system, :perms, :sort, datetime('now'), datetime('now'))"
            ).bindparams(
                id=str(uuid.uuid4()),
                name=name,
                slug=slug,
                is_system=1 if is_system else 0,
                perms=json.dumps(perms),
                sort=sort,
            )
        )

    # --- Backfill existing admins ------------------------------------------- #
    # For every user currently marked as an admin, create an AdminProfile
    # with the super_admin role so access is preserved.
    super_admin = conn.execute(
        sa.text("SELECT id FROM admin_roles WHERE slug = 'super_admin'")
    ).scalar_one_or_none()

    admin_users = conn.execute(
        sa.text("SELECT id FROM users WHERE role = 'admin'")
    ).fetchall()

    if super_admin:
        for (user_id,) in admin_users:
            conn.execute(
                sa.text(
                    "INSERT OR IGNORE INTO admin_profiles "
                    "(id, user_id, role_id, status, added_at, created_at, updated_at) "
                    "VALUES (:id, :uid, :role, 'active', datetime('now'), datetime('now'), datetime('now'))"
                ).bindparams(
                    id=str(uuid.uuid4()),
                    uid=user_id,
                    role=super_admin,
                )
            )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_admin_logs_session_id'), table_name='admin_logs')
    op.drop_column('admin_logs', 'session_id')
    op.drop_index(op.f('ix_admin_profiles_user_id'), table_name='admin_profiles')
    op.drop_index(op.f('ix_admin_profiles_status'), table_name='admin_profiles')
    op.drop_index(op.f('ix_admin_profiles_role_id'), table_name='admin_profiles')
    op.drop_table('admin_profiles')
    op.drop_index(op.f('ix_admin_roles_slug'), table_name='admin_roles')
    op.drop_table('admin_roles')
