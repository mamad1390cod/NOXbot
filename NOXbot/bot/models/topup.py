"""Wallet top-up models — TopUpRequest, TopUpAmount, TopUpReceipt."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class TopUpStatus(str, enum.Enum):
    """Status of a wallet top-up request."""

    PENDING = "pending"
    WAITING_FOR_RECEIPT = "waiting_for_receipt"
    UNDER_REVIEW = "under_review"
    WAITING_FOR_NEW_RECEIPT = "waiting_for_new_receipt"
    APPROVED = "approved"
    REJECTED = "rejected"

    @property
    def label(self) -> str:
        return TOPUP_STATUS_LABELS[self]


TOPUP_STATUS_LABELS = {
    TopUpStatus.PENDING: "در انتظار",
    TopUpStatus.WAITING_FOR_RECEIPT: "در انتظار رسید",
    TopUpStatus.UNDER_REVIEW: "در حال بررسی",
    TopUpStatus.WAITING_FOR_NEW_RECEIPT: "نیازمند رسید مجدد",
    TopUpStatus.APPROVED: "تأیید شده",
    TopUpStatus.REJECTED: "رد شده",
}


class TopUpPaymentMethod(str, enum.Enum):
    """Payment methods for top-up."""

    CARD = "card"
    CRYPTO = "crypto"

    @property
    def label(self) -> str:
        return {"card": "کارت به کارت", "crypto": "ارز دیجیتال"}[self.value]


class TopUpAmount(Base, UUIDMixin, TimestampMixin):
    """Admin-configurable preset amounts for wallet top-up."""

    __tablename__ = "topup_amounts"

    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="IRR",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<TopUpAmount(id={self.id}, amount={self.amount}, active={self.is_active})>"


class TopUpRequest(Base, UUIDMixin, TimestampMixin):
    """A wallet top-up request from a user."""

    __tablename__ = "topup_requests"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="IRR",
        nullable=False,
    )
    payment_method: Mapped[TopUpPaymentMethod] = mapped_column(
        Enum(TopUpPaymentMethod),
        default=TopUpPaymentMethod.CARD,
        nullable=False,
    )
    status: Mapped[TopUpStatus] = mapped_column(
        Enum(TopUpStatus),
        default=TopUpStatus.PENDING,
        nullable=False,
        index=True,
    )
    tracking_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="topup_requests",
        foreign_keys=[user_id],
    )
    reviewed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by_id],
    )
    receipts: Mapped[list["TopUpReceipt"]] = relationship(
        "TopUpReceipt",
        back_populates="topup_request",
        cascade="all, delete-orphan",
        order_by="TopUpReceipt.created_at",
    )

    @property
    def is_pending(self) -> bool:
        return self.status in (
            TopUpStatus.PENDING,
            TopUpStatus.WAITING_FOR_RECEIPT,
            TopUpStatus.UNDER_REVIEW,
            TopUpStatus.WAITING_FOR_NEW_RECEIPT,
        )

    @property
    def is_finalized(self) -> bool:
        return self.status in (TopUpStatus.APPROVED, TopUpStatus.REJECTED)

    @property
    def latest_receipt(self) -> "TopUpReceipt | None":
        if self.receipts:
            return self.receipts[-1]
        return None

    def __repr__(self) -> str:
        return f"<TopUpRequest(tracking={self.tracking_code}, amount={self.amount}, status={self.status})>"


class TopUpReceipt(Base, UUIDMixin, TimestampMixin):
    """A receipt file submitted for a top-up request (supports resubmission)."""

    __tablename__ = "topup_receipts"

    topup_request_id: Mapped[str] = mapped_column(
        ForeignKey("topup_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        default="photo",
        nullable=False,
    )
    submission_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    submitted_by_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    topup_request: Mapped["TopUpRequest"] = relationship(
        "TopUpRequest",
        back_populates="receipts",
    )
    submitted_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[submitted_by_id],
    )

    def __repr__(self) -> str:
        return f"<TopUpReceipt(request={self.topup_request_id}, submission={self.submission_number})>"
