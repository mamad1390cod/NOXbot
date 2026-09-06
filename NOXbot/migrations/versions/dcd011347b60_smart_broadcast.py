"""smart broadcast

Revision ID: dcd011347b60
Revises: 01e6ad582361
Create Date: 2026-08-06 03:40:00.000000

Notes:
- Creates broadcasts and broadcast_templates tables.
- Adds users.notification_preferences for per-category opt-in/out.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcd011347b60'
down_revision: Union[str, Sequence[str], None] = '01e6ad582361'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'broadcast_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('media_file_id', sa.String(length=500), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('buttons', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'broadcasts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('audience', sa.Text(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('media_file_id', sa.String(length=500), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('buttons', sa.Text(), nullable=True),
        sa.Column('poll', sa.Text(), nullable=True),
        sa.Column('notification_category', sa.String(length=30), nullable=False),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('interval_seconds', sa.BigInteger(), nullable=True),
        sa.Column('total_target', sa.Integer(), nullable=False),
        sa.Column('sent_count', sa.Integer(), nullable=False),
        sa.Column('failed_count', sa.Integer(), nullable=False),
        sa.Column('blocked_count', sa.Integer(), nullable=False),
        sa.Column('opted_out_count', sa.Integer(), nullable=False),
        sa.Column('failed_ids', sa.Text(), nullable=True),
        sa.Column('blocked_ids', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_broadcasts_scheduled_at'), 'broadcasts', ['scheduled_at'])
    op.create_index('ix_broadcasts_scheduled_status', 'broadcasts', ['scheduled_at', 'status'])
    op.create_index(op.f('ix_broadcasts_status'), 'broadcasts', ['status'])

    op.add_column('users', sa.Column('notification_preferences', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'notification_preferences')
    op.drop_index(op.f('ix_broadcasts_status'), table_name='broadcasts')
    op.drop_index('ix_broadcasts_scheduled_status', table_name='broadcasts')
    op.drop_index(op.f('ix_broadcasts_scheduled_at'), table_name='broadcasts')
    op.drop_table('broadcasts')
    op.drop_table('broadcast_templates')