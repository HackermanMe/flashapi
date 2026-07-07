from __future__ import annotations

from typing import Any, get_origin, get_args

from flashapi.core.schema import FieldSchema, FieldType, ModelSchema
from flashapi.core.pluralize import pluralize
from flashapi.inspectors.base import Inspector

TYPE_MAP: dict[type, FieldType] = {
    str: FieldType.STRING,
    int: FieldType.INTEGER,
    float: FieldType.FLOAT,
    bool: FieldType.BOOLEAN,
}


class PydanticInspector(Inspector):
    def inspect(self, model_class: type, plural: str | None = None) -> ModelSchema:
        from pydantic import BaseModel
        from pydantic.fields import FieldInfo

        if not issubclass(model_class, BaseModel):
            raise TypeError(f"{model_class} is not a Pydantic model")

        fields: list[FieldSchema] = []
        fields.append(FieldSchema(name="id", type=FieldType.INTEGER, required=False, primary_key=True))

        for name, field_info in model_class.model_fields.items():
            field_type = self._resolve_type(field_info.annotation)
            constraints = self._extract_constraints(field_info)
            required = field_info.is_required()
            default = field_info.default if not required else None

            fields.append(FieldSchema(
                name=name,
                type=field_type,
                required=required,
                default=default,
                constraints=constraints,
            ))

        model_name = model_class.__name__
        plural_name = plural or pluralize(model_name)

        return ModelSchema(name=model_name, plural=plural_name, fields=fields)

    def _resolve_type(self, annotation: Any) -> FieldType:
        if annotation is None:
            return FieldType.STRING

        origin = get_origin(annotation)
        if origin is not None:
            args = get_args(annotation)
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                annotation = non_none[0]
            else:
                return FieldType.STRING

        return TYPE_MAP.get(annotation, FieldType.STRING)

    def _extract_constraints(self, field_info: Any) -> dict:
        constraints = {}
        metadata = getattr(field_info, "metadata", [])
        for m in metadata:
            if hasattr(m, "max_length"):
                constraints["max_length"] = m.max_length
            if hasattr(m, "min_length"):
                constraints["min_length"] = m.min_length
            if hasattr(m, "ge"):
                constraints["min_value"] = m.ge
            if hasattr(m, "le"):
                constraints["max_value"] = m.le
        return constraints
