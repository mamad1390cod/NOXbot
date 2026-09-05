"""Product model."""

import enum
from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class ProductType(str, enum.Enum):
    """Product types."""

    PHYSICAL = "physical"  # Requires shipping
    DIGITAL = "digital"  # Digital delivery
    ACCOUNT = "account"  # Game account (username/password)
    SERVICE = "service"  # Service like boosting


class ProductStatus(str, enum.Enum):
    """Product status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    HIDDEN = "hidden"


class Product(Base, UUIDMixin, TimestampMixin):
    """Product model."""

    __tablename__ = "products"

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
    type: Mapped[ProductType] = mapped_column(
        Enum(ProductType),
        default=ProductType.DIGITAL,
        nullable=False,
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus),
        default=ProductStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    price: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )  # Price in Tomans
    original_price: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )  # For discounts
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
    min_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    max_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    requires_account_info: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # For account type products
    account_fields: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON: ["username", "email", "password"]
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    gallery: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON array of image URLs
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

    # Foreign keys
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="products",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        if self.unlimited_stock:
            return True
        return self.stock > 0

    @property
    def discounted_price(self) -> int:
        """Get effective price (with discount if applicable)."""
        if self.original_price and self.original_price > self.price:
            return self.price
        return self.price

    @property
    def discount_percent(self) -> int:
        """Calculate discount percentage."""
        if self.original_price and self.original_price > self.price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title={self.title}, price={self.price}, status={self.status})>"