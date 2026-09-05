"""advanced order management

Revision ID: bce07f0691f7
Revises: eac5d45ed12c
Create Date: 2026-08-06 00:20:54.015727

Notes:
- Adds human-readable order_number (NOX-YYYY-NNNNNN).
- Adds full lifecycle timestamps, admin attribution FKs, notes, ETA and
  linked-ticket column to orders.
- Adds order_status_events table for the audit trail.
- Data migration maps old statuses to the new lifecycle and backfills
  order_number for existing rows.

SQLite cannot ALTER constraints, so the orders table is rebuilt via
op.batch_alter_table (copy-and-move strategy). Because the status column is
stored as VARCHAR and SQLite does not enforce length, the enum values are
migrated as data only.
"""

from typing import Sequence, Union
from collections import defaultdict

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bce07f0691f7'
down_revision: Union[str, Sequence[str], None] = 'eac5d45ed12c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Order status events table ----------------------------------------- #
    op.create_table(
        'order_status_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('from_status', sa.String(length=30), nullable=True),
        sa.Column('to_status', sa.String(length=30), nullable=False),
        sa.Column('changed_by_id', sa.String(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_status_events_order_id', 'order_status_events', ['order_id'])
    op.create_index('ix_order_status_events_order_created', 'order_status_events', ['order_id', 'created_at'])

    # --- Rebuild orders table with the new columns (batch mode) ------------- #
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('order_number', sa.String(length=30), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('internal_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('customer_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('refund_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('payment_uploaded_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('payment_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('preparing_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('estimated_delivery_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('actual_delivered_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_by_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('delivered_by_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('cancelled_by_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('rejected_by_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('linked_ticket_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('custom_registration_id', sa.String(), nullable=True))

        batch_op.create_foreign_key('fk_orders_custom_registration_id', 'custom_registrations', ['custom_registration_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_orders_rejected_by_id', 'users', ['rejected_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_orders_approved_by_id', 'users', ['approved_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_orders_delivered_by_id', 'users', ['delivered_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_orders_cancelled_by_id', 'users', ['cancelled_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_orders_linked_ticket_id', 'tickets', ['linked_ticket_id'], ['id'], ondelete='SET NULL')

        batch_op.create_index(op.f('ix_orders_approved_by_id'), ['approved_by_id'])
        batch_op.create_index(op.f('ix_orders_cancelled_by_id'), ['cancelled_by_id'])
        batch_op.create_index(op.f('ix_orders_custom_registration_id'), ['custom_registration_id'])
        batch_op.create_index(op.f('ix_orders_delivered_by_id'), ['delivered_by_id'])
        batch_op.create_index(op.f('ix_orders_linked_ticket_id'), ['linked_ticket_id'])
        batch_op.create_index(op.f('ix_orders_rejected_by_id'), ['rejected_by_id'])
        batch_op.create_index('ix_orders_status_created', ['status', 'created_at'])

        # --- Data migration ----------------------------------------------------- #
    # Preserve the old free-form `notes` into internal_notes (column now exists).
    op.execute(
        sa.text(
            "UPDATE orders SET internal_notes = notes "
            "WHERE notes IS NOT NULL AND notes != ''"
        )
    )

    # Map old lifecycle values to the new status names.
    old_to_new = {
        'paid': 'approved',
        'processing': 'preparing',
        'pending': 'waiting_payment',
    }
    for old, new in old_to_new.items():
        op.execute(
            sa.text("UPDATE orders SET status = :new WHERE status = :old").bindparams(old=old, new=new)
        )

    # Backfill order_number for existing rows: NOX-<year>-<seq>.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, strftime('%Y', created_at) AS yr FROM orders "
            "WHERE order_number = '' ORDER BY created_at"
        )
    ).fetchall()

    counters: dict[str, int] = defaultdict(int)
    for row_id, yr in rows:
        counters[yr] += 1
        num = f"NOX-{yr}-{counters[yr]:06d}"
        conn.execute(
            sa.text("UPDATE orders SET order_number = :num WHERE id = :id").bindparams(num=num, id=row_id)
        )

    # Order number is unique for new orders; drop the temporary server default.
    with op.batch_alter_table('orders') as batch_op:
        batch_op.alter_column(
            'order_number',
            existing_type=sa.String(length=30),
            existing_server_default='',
            server_default=None,
            nullable=False,
        )
        batch_op.create_index(op.f('ix_orders_order_number'), ['order_number'], unique=True)

    # Remove obsolete columns now that their data has been migrated.
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('tracking_code')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_order_status_events_order_id'), table_name='order_status_events')
    op.drop_index('ix_order_status_events_order_created', table_name='order_status_events')
    op.drop_table('order_status_events')

    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('tracking_code', sa.VARCHAR(length=100), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.TEXT(), nullable=True))
        batch_op.drop_index(op.f('ix_orders_order_number'))
        batch_op.drop_index('ix_orders_status_created')
        batch_op.drop_index(op.f('ix_orders_rejected_by_id'))
        batch_op.drop_index(op.f('ix_orders_linked_ticket_id'))
        batch_op.drop_index(op.f('ix_orders_delivered_by_id'))
        batch_op.drop_index(op.f('ix_orders_custom_registration_id'))
        batch_op.drop_index(op.f('ix_orders_cancelled_by_id'))
        batch_op.drop_index(op.f('ix_orders_approved_by_id'))
        batch_op.drop_constraint('fk_orders_linked_ticket_id', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_cancelled_by_id', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_delivered_by_id', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_approved_by_id', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_rejected_by_id', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_custom_registration_id', type_='foreignkey')
        batch_op.drop_column('custom_registration_id')
        batch_op.drop_column('linked_ticket_id')
        batch_op.drop_column('rejected_by_id')
        batch_op.drop_column('cancelled_by_id')
        batch_op.drop_column('delivered_by_id')
        batch_op.drop_column('approved_by_id')
        batch_op.drop_column('actual_delivered_at')
        batch_op.drop_column('estimated_delivery_at')
        batch_op.drop_column('rejected_at')
        batch_op.drop_column('refunded_at')
        batch_op.drop_column('cancelled_at')
        batch_op.drop_column('delivered_at')
        batch_op.drop_column('preparing_at')
        batch_op.drop_column('approved_at')
        batch_op.drop_column('payment_reviewed_at')
        batch_op.drop_column('payment_uploaded_at')
        batch_op.drop_column('refund_reason')
        batch_op.drop_column('rejection_reason')
        batch_op.drop_column('cancellation_reason')
        batch_op.drop_column('customer_notes')
        batch_op.drop_column('internal_notes')
        batch_op.drop_column('order_number')
