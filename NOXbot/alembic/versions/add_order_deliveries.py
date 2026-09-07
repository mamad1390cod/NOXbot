"""add order deliveries table

Revision ID: add_order_deliveries
Revises: add_emoji_custom_cat
Create Date: 2026-09-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_order_deliveries'
down_revision = 'add_emoji_custom_cat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'order_deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('delivery_type', sa.String(50), nullable=False, server_default='config_text'),
        sa.Column('config_text', sa.Text(), nullable=True),
        sa.Column('file_id', sa.String(255), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_order_deliveries_order_id', 'order_deliveries', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_order_deliveries_order_id', table_name='order_deliveries')
    op.drop_table('order_deliveries')
