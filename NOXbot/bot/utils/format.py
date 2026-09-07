"""Formatting utilities."""


def format_price(amount: int | float) -> str:
    """Format a number with thousands separators, Persian digits."""
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return "0"
    # Format with commas then convert to Persian digits
    s = f"{amount:,}"
    return s.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def format_number(num: int | float) -> str:
    """Format number with commas."""
    return f"{num:,}"


def truncate(text: str, max_len: int = 50, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def price_with_unit(amount: int, unit: str = "تومان") -> str:
    """Format price with unit."""
    return f"{format_price(amount)} {unit}"