from __future__ import annotations

from typing import Any


def apply_search(
    items: list[dict[str, Any]],
    query: str | None,
    searchable_fields: set[str],
) -> list[dict[str, Any]]:
    """Filter items where any searchable field contains the query string."""
    if not query:
        return items

    query_lower = query.lower()
    result = []

    for item in items:
        for field_name in searchable_fields:
            value = item.get(field_name, "")
            if value and query_lower in str(value).lower():
                result.append(item)
                break

    return result
