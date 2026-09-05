"""anti abuse system

Revision ID: 665eb9a26744
Revises: f64d5aee9b54
Create Date: 2026-08-06 02:56:54.567524

Notes:
- Creates abuse_events and auto_actions tables.
- Adds anti-abuse columns to users with proper server defaults.
- The enum fields are stored as VARCHAR in SQLite (no length enforcement).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '665eb9a26744'
down_revision: Union[str, Sequence[str], None] = 'f64d5aee9b54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'abuse_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('event_data', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_abuse_events_type'), 'abuse_events', ['type'])
    op.create_index('ix_abuse_events_user_created', 'abuse_events', ['user_id', 'created_at'])
    op.create_index(op.f('ix_abuse_events_user_id'), 'abuse_events', ['user_id'])

    op.create_table(
        'auto_actions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.BigInteger(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('is_manual', sa.Boolean(), nullable=False),
        sa.Column('admin_applied_by', sa.String(), nullable=True),
        sa.Column('lifted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['admin_applied_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auto_actions_action'), 'auto_actions', ['action'])
    op.create_index(op.f('ix_auto_actions_user_id'), 'auto_actions', ['user_id'])

    op.add_column('users', sa.Column('violation_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('muted_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('abuse_suspended_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('whitelisted', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('blacklisted', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('blacklist_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'blacklist_reason')
    op.drop_column('users', 'blacklisted')
    op.drop_column('users', 'whitelisted')
    op.drop_column('users', 'abuse_suspended_until')
    op.drop_column('users', 'muted_until')
    op.drop_column('users', 'violation_count')
    op.drop_index(op.f('ix_auto_actions_user_id'), table_name='auto_actions')
    op.drop_index(op.f('ix_auto_actions_action'), table_name='auto_actions')
    op.drop_table('auto_actions')
    op.drop_index(op.f('ix_abuse_events_user_id'), table_name='abuse_events')
    op.drop_index('ix_abuse_events_user_created', table_name='abuse_events')
    op.drop_index(op.f('ix_abuse_events_type'), table_name='abuse_events')
    op.drop_table('abuse_events')