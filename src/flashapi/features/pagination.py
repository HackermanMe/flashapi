from __future__ import annotations

from typing import Any

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def paginate(
    items: list[dict[str, Any]],
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], int]:
    """Return a page slice and total count."""
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    page = max(1, page)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total
