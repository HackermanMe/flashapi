from __future__ import annotations

from typing import Any


def apply_sorting(
    items: list[dict[str, Any]],
    sort: str | None,
    valid_fields: set[str],
) -> list[dict[str, Any]]:
    """Sort items by field. Prefix with - for descending."""
    if not sort:
        return items

    descending = sort.startswith("-")
    field_name = sort.lstrip("-")

    if field_name not in valid_fields:
        return items

    return sorted(items, key=lambda x: x.get(field_name, ""), reverse=descending)
