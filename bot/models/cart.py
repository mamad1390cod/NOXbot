"""Cart models."""

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class Cart(Base, UUIDMixin, TimestampMixin):
    """Shopping cart for regular products and configs."""

    __tablename__ = "carts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="cart",
    )
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    @property
    def total_items(self) -> int:
        """Get total number of items in cart."""
        return sum(item.quantity for item in self.items)

    @property
    def total_price(self) -> int:
        """Calculate total price."""
        total = 0
        for item in self.items:
            if item.product:
                total += item.product.discounted_price * item.quantity
            elif item.config_product:
                total += item.config_product.price * item.quantity
        return total

    def __repr__(self) -> str:
        return f"<Cart(id={self.id}, user_id={self.user_id}, items={self.total_items})>"


class CartItem(Base, UUIDMixin, TimestampMixin):
    """Individual item in shopping cart."""

    __tablename__ = "cart_items"

    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    config_product_id: Mapped[str | None] = mapped_column(
        ForeignKey("config_products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    # For account type products - store account info
    account_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # JSON: {"username": "...", "email": "...", "password": "..."}

    # Relationships
    cart: Mapped["Cart"] = relationship(
        "Cart",
        back_populates="items",
    )
    product: Mapped["Product | None"] = relationship(
        "Product",
        back_populates="cart_items",
    )
    config_product: Mapped["ConfigProduct | None"] = relationship(
        "ConfigProduct",
        back_populates="cart_items",
    )

    @property
    def item_type(self) -> str:
        """Get item type."""
        if self.product_id:
            return "product"
        if self.config_product_id:
            return "config"
        return "unknown"

    @property
    def title(self) -> str:
        """Get item title."""
        if self.product:
            return self.product.title
        if self.config_product:
            return self.config_product.title
        return "نامشخص"

    @property
    def price(self) -> int:
        """Get item price."""
        if self.product:
            return self.product.discounted_price
        if self.config_product:
            return self.config_product.price
        return 0

    @property
    def total_price(self) -> int:
        """Get total price for this line item."""
        return self.price * self.quantity

    def __repr__(self) -> str:
        return f"<CartItem(id={self.id}, cart_id={self.cart_id}, qty={self.quantity})>"