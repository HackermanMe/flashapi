"""Field visibility rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flashapi.core.schema import ModelSchema


def response_fields(schema: ModelSchema) -> set[str]:
    """Fields visible in GET responses."""
    return {
        f.name for f in schema.fields
        if not f.hidden and not f.writeonly
    }


def writable_fields(schema: ModelSchema) -> set[str]:
    """Fields accepted in POST/PUT bodies."""
    return {
        f.name for f in schema.fields
        if not f.hidden and not f.readonly and not f.primary_key
        and not f.auto_generated and not f.auto
    }


def export_fields(schema: ModelSchema) -> set[str]:
    """Fields included in exports."""
    return {
        f.name for f in schema.fields
        if not f.hidden and not f.writeonly and not f.export_exclude
    }


def filter_response(data: dict, schema: ModelSchema) -> dict:
    """Remove hidden/writeonly fields from a response dict."""
    visible = response_fields(schema)
    schema_field_names = {f.name for f in schema.fields}
    return {k: v for k, v in data.items() if k in visible or k == "id" or k not in schema_field_names}


def filter_input(data: dict, schema: ModelSchema) -> dict:
    """Remove readonly/hidden fields from input dict."""
    allowed = writable_fields(schema)
    return {k: v for k, v in data.items() if k in allowed}


def select_fields(data: dict, fields: list[str] | None, schema: ModelSchema) -> dict:
    """
    Select only requested fields from response data.

    Field selection (?fields=id,name,price) allows clients to request only specific fields,
    reducing payload size and improving performance.

    Args:
        data: Response dict to filter
        fields: List of field names to include (None = return all visible fields)
        schema: Model schema for validation

    Returns:
        Dict containing only requested fields that exist and are visible (id always included)

    Example:
        >>> select_fields({"id": 1, "name": "Laptop", "price": 999, "stock": 10}, ["name"], schema)
        {"id": 1, "name": "Laptop"}  # id always included
    """
    if not fields:
        return data

    # Get visible fields from schema
    visible = response_fields(schema)

    # Filter: requested fields + always include id
    result = {}
    for k, v in data.items():
        if k == "id":
            result[k] = v  # Always include id
        elif k in fields and k in visible:
            result[k] = v

    return result
