from __future__ import annotations

from typing import Any


def apply_sorting(
    items: list[dict[str, Any]],
    sort: str | None,
    valid_fields: set[str],
) -> list[dict[str, Any]]:
    """Sort items by field. Format: 'field,asc' or 'field,desc'."""
    if not sort:
        return items

    parts = sort.split(",", 1)
    field_name = parts[0].strip()
    direction = parts[1].strip().lower() if len(parts) > 1 else "asc"
    descending = direction == "desc"

    if field_name not in valid_fields:
        return items

    return sorted(items, key=lambda x: x.get(field_name, ""), reverse=descending)
