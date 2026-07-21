from __future__ import annotations

from typing import Any

DEFAULT_SIZE = 20
MAX_SIZE = 100


def paginate(
    items: list[dict[str, Any]],
    page: int = 0,
    size: int = DEFAULT_SIZE,
) -> tuple[list[dict[str, Any]], int]:
    """Return a page slice and total count. Page is 0-indexed."""
    size = min(max(1, size), MAX_SIZE)
    page = max(0, page)
    total = len(items)
    start = page * size
    end = start + size
    return items[start:end], total
