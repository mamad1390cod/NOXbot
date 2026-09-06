"""wallet_topup_system

Revision ID: a7b3c9d2e1f4
Revises: f64d5aee9b54
Create Date: 2026-09-04

Adds wallet top-up system: TopUpAmount, TopUpRequest, TopUpReceipt models.
Extends Transaction with balance_before and admin_id columns.
Adds new TransactionType enum values: topup, admin_credit, admin_debit, purchase.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a7b3c9d2e1f4"
down_revision = "f64d5aee9b54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add balance_before and admin_id to transactions ─────────────── #
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("balance_before", sa.BigInteger(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("admin_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    # ── 2. Create topup_amounts ────────────────────────────────────────── #
    op.create_table(
        "topup_amounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="IRR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 3. Create topup_requests ───────────────────────────────────────── #
    op.create_table(
        "topup_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="IRR"),
        sa.Column("payment_method", sa.Enum("card", "crypto", name="topuppaymentmethod"), nullable=False, server_default="card"),
        sa.Column("status", sa.Enum("pending", "waiting_for_receipt", "under_review", "waiting_for_new_receipt", "approved", "rejected", name="topupstatus"), nullable=False, server_default="pending", index=True),
        sa.Column("tracking_code", sa.String(30), nullable=False, unique=True, index=True),
        sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 4. Create topup_receipts ───────────────────────────────────────── #
    op.create_table(
        "topup_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("topup_request_id", sa.String(36), sa.ForeignKey("topup_requests.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_id", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False, server_default="photo"),
        sa.Column("submission_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 5. Seed default top-up amounts ─────────────────────────────────── #
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    defaults = [
        (10_000, "10 هزار تومان", 1),
        (20_000, "20 هزار تومان", 2),
        (50_000, "50 هزار تومان", 3),
        (100_000, "100 هزار تومان", 4),
        (200_000, "200 هزار تومان", 5),
        (500_000, "500 هزار تومان", 6),
    ]
    for amount, label, order in defaults:
        op.execute(
            sa.text(
                "INSERT INTO topup_amounts (id, amount, currency, is_active, display_order, label, created_at, updated_at) "
                "VALUES (:id, :amount, 'IRR', 1, :order, :label, :now, :now)"
            ).bindparams(
                id=str(uuid.uuid4()),
                amount=amount,
                order=order,
                label=label,
                now=now,
            )
        )


def downgrade() -> None:
    op.drop_table("topup_receipts")
    op.drop_table("topup_requests")
    op.drop_table("topup_amounts")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("admin_id")
        batch.drop_column("balance_before")
    # Note: SQLite doesn't support DROP TYPE for enums easily; left as-is.
