"""Field visibility rules."""

from __future__ import annotations

from flashapi.core.schema import FieldSchema, ModelSchema


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
