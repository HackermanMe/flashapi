from __future__ import annotations

from dataclasses import fields as dc_fields, MISSING
from typing import Any

from flashapi.core.schema import FieldSchema, FieldType, ModelSchema
from flashapi.core.pluralize import pluralize
from flashapi.inspectors.base import Inspector

TYPE_MAP: dict[type, FieldType] = {
    str: FieldType.STRING,
    int: FieldType.INTEGER,
    float: FieldType.FLOAT,
    bool: FieldType.BOOLEAN,
}


class DataclassInspector(Inspector):
    def inspect(self, model_class: type, plural: str | None = None) -> ModelSchema:
        schema_fields: list[FieldSchema] = []
        schema_fields.append(
            FieldSchema(name="id", type=FieldType.INTEGER, required=False, primary_key=True)
        )

        for f in dc_fields(model_class):
            field_type = TYPE_MAP.get(f.type, FieldType.STRING)
            required = f.default is MISSING and f.default_factory is MISSING
            default = None if required else f.default

            schema_fields.append(FieldSchema(
                name=f.name,
                type=field_type,
                required=required,
                default=default,
            ))

        model_name = model_class.__name__
        plural_name = plural or pluralize(model_name)

        return ModelSchema(name=model_name, plural=plural_name, fields=schema_fields)
