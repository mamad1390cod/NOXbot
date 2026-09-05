"""Feature flags — map semantic features to their settings keys."""

import enum


class Feature(str, enum.Enum):
    """Semantic feature flags backed by boolean settings keys."""

    PRODUCTS = "feature_products"
    CONFIGS = "feature_configs"
    CUSTOMS = "feature_customs"
    ORDERS = "feature_orders"
    SUPPORT = "feature_support"
    REFERRAL = "feature_referral"
    DISCOUNTS = "feature_discounts"
    CARD_PAYMENT = "feature_card_payment"
    MAINTENANCE_MODE = "feature_maintenance_mode"

    @property
    def label(self) -> str:
        return FEATURE_LABELS[self]


FEATURE_LABELS: dict[Feature, str] = {
    Feature.PRODUCTS: "محصولات",
    Feature.CONFIGS: "کانفیگ‌ها",
    Feature.CUSTOMS: "کاستوم‌ها",
    Feature.ORDERS: "سفارش‌ها",
    Feature.SUPPORT: "پشتیبانی",
    Feature.REFERRAL: "سیستم معرفی",
    Feature.DISCOUNTS: "تخفیف‌ها",
    Feature.CARD_PAYMENT: "پرداخت کارتی",
    Feature.MAINTENANCE_MODE: "حالت تعمیرات",
}