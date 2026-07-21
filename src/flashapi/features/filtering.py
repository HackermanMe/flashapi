from __future__ import annotations

from typing import Any

RESERVED_PARAMS = {"page", "size", "sort", "search", "deleted", "expand", "format"}


def apply_filters(
    items: list[dict[str, Any]],
    filters: dict[str, str],
    valid_fields: set[str],
) -> list[dict[str, Any]]:
    """Filter items by exact field match."""
    active_filters = {
        k: v for k, v in filters.items()
        if k not in RESERVED_PARAMS and k in valid_fields
    }

    if not active_filters:
        return items

    result = []
    for item in items:
        match = True
        for field_name, value in active_filters.items():
            item_value = item.get(field_name)
            if str(item_value) != str(value):
                match = False
                break
        if match:
            result.append(item)

    return result
