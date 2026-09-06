"""Pagination utilities."""

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class PaginationResult:
    """Result of a pagination operation."""

    items: Sequence[Any]
    total: int
    page: int
    total_pages: int
    has_prev: bool
    has_next: bool
    per_page: int = 10

    @property
    def start_index(self) -> int:
        return self.page * self.per_page + 1

    @property
    def end_index(self) -> int:
        return self.page * self.per_page + len(self.items)


def paginate(
    items: Sequence[Any],
    page: int,
    per_page: int,
    total: int | None = None,
) -> PaginationResult:
    """Paginate a sequence of items."""
    if page < 0:
        page = 0

    total_items = total if total is not None else len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages - 1)

    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    return PaginationResult(
        items=page_items,
        total=total_items,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        has_prev=page > 0,
        has_next=page < total_pages - 1,
    )