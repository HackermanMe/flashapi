from __future__ import annotations

from typing import Any

RESERVED_PARAMS = {"page", "size", "sort", "search", "deleted", "expand", "format", "fields"}

OPERATORS = frozenset({
    "eq", "neq", "gt", "gte", "lt", "lte",
    "contains", "startswith", "endswith", "isnull", "in",
})


def _parse_filter_key(key: str) -> tuple[str, str]:
    """Parse 'field.operator' into (field_name, operator). Default operator is 'eq'."""
    dot = key.rfind(".")
    if dot > 0 and dot < len(key) - 1:
        possible_op = key[dot + 1:]
        if possible_op in OPERATORS:
            return key[:dot], possible_op
    return key, "eq"


def _convert(value: str, item_value: Any) -> Any:
    """Convert string value to the same type as the item's field value."""
    if item_value is None:
        return value
    target_type = type(item_value)
    if target_type is str:
        return value
    if target_type is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if target_type is float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    if target_type is bool:
        return value.lower() in ("true", "1", "yes")
    return value


def _match_operator(item_value: Any, op: str, filter_value: str) -> bool:
    """Evaluate a single filter operator against an item's field value."""
    if op == "isnull":
        is_null = item_value is None
        return is_null if filter_value.lower() in ("true", "1", "yes") else not is_null

    if op == "in":
        parts = [p.strip() for p in filter_value.split(",")]
        str_val = str(item_value) if item_value is not None else ""
        converted = []
        for p in parts:
            converted.append(_convert(p, item_value))
        return item_value in converted or str_val in parts

    if item_value is None:
        return False

    if op == "eq":
        converted = _convert(filter_value, item_value)
        return item_value == converted or str(item_value) == str(filter_value)

    if op == "neq":
        converted = _convert(filter_value, item_value)
        return item_value != converted and str(item_value) != str(filter_value)

    if op == "contains":
        return filter_value.lower() in str(item_value).lower()

    if op == "startswith":
        return str(item_value).lower().startswith(filter_value.lower())

    if op == "endswith":
        return str(item_value).lower().endswith(filter_value.lower())

    # Comparison operators
    converted = _convert(filter_value, item_value)
    try:
        if op == "gt":
            return item_value > converted
        if op == "gte":
            return item_value >= converted
        if op == "lt":
            return item_value < converted
        if op == "lte":
            return item_value <= converted
    except TypeError:
        return False

    return False


def apply_filters(
    items: list[dict[str, Any]],
    filters: dict[str, str],
    valid_fields: set[str],
) -> list[dict[str, Any]]:
    """Filter items using operators: ?field.operator=value (default operator: eq)."""
    parsed_filters: list[tuple[str, str, str]] = []
    for key, value in filters.items():
        if key in RESERVED_PARAMS:
            continue
        field_name, op = _parse_filter_key(key)
        if field_name in valid_fields:
            parsed_filters.append((field_name, op, value))

    if not parsed_filters:
        return items

    result = []
    for item in items:
        match = True
        for field_name, op, value in parsed_filters:
            item_value = item.get(field_name)
            if not _match_operator(item_value, op, value):
                match = False
                break
        if match:
            result.append(item)

    return result
