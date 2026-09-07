"""Category model for products and configs."""

from sqlalchemy import (
    Boolean,
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class Category(Base, UUIDMixin, TimestampMixin):
    """Unified category model for products, configs, and customs."""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    name_en: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # product, config, custom, ticket
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="children",
        remote_side="Category.id",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="category",
        cascade="all, delete-orphan",
    )
    config_products: Mapped[list["ConfigProduct"]] = relationship(
        "ConfigProduct",
        back_populates="category",
        cascade="all, delete-orphan",
    )
    ticket_categories: Mapped[list["TicketCategory"]] = relationship(
        "TicketCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name}, type={self.type})>"