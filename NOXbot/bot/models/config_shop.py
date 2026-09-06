"""Config shop models."""

import enum
from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class ConfigProductStatus(str, enum.Enum):
    """Config product status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    HIDDEN = "hidden"


class ConfigProduct(Base, UUIDMixin, TimestampMixin):
    """Config product model."""

    __tablename__ = "config_products"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    title_en: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    short_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[ConfigProductStatus] = mapped_column(
        Enum(ConfigProductStatus),
        default=ConfigProductStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    price: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    original_price: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    stock: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    unlimited_stock: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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
    gallery: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    purchase_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    config_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON: config file content or download link
    delivery_method: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )  # manual, auto_link, file

    # Foreign keys
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="config_products",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="config_product",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="config_product",
        cascade="all, delete-orphan",
    )

    @property
    def is_in_stock(self) -> bool:
        """Check if config is in stock."""
        if self.unlimited_stock:
            return True
        return self.stock > 0

    @property
    def discounted_price(self) -> int:
        """Get effective price."""
        if self.original_price and self.original_price > self.price:
            return self.price
        return self.price

    def __repr__(self) -> str:
        return f"<ConfigProduct(id={self.id}, title={self.title}, price={self.price}, status={self.status})>"


class ConfigCategory(Base, UUIDMixin, TimestampMixin):
    """Config product category model."""

    __tablename__ = "config_categories"

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

    # Foreign key
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ConfigCategory(id={self.id}, name={self.name})>"