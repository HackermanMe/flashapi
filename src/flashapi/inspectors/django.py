from __future__ import annotations

from flashapi.core.schema import FieldSchema, FieldType, ModelSchema, RelationSchema
from flashapi.core.pluralize import pluralize
from flashapi.inspectors.base import Inspector

DJANGO_TYPE_MAP = {
    "AutoField": FieldType.INTEGER,
    "BigAutoField": FieldType.INTEGER,
    "SmallAutoField": FieldType.INTEGER,
    "CharField": FieldType.STRING,
    "TextField": FieldType.TEXT,
    "IntegerField": FieldType.INTEGER,
    "BigIntegerField": FieldType.INTEGER,
    "SmallIntegerField": FieldType.INTEGER,
    "PositiveIntegerField": FieldType.INTEGER,
    "FloatField": FieldType.FLOAT,
    "DecimalField": FieldType.FLOAT,
    "BooleanField": FieldType.BOOLEAN,
    "DateField": FieldType.DATE,
    "DateTimeField": FieldType.DATETIME,
    "TimeField": FieldType.TIME,
    "UUIDField": FieldType.UUID,
    "JSONField": FieldType.JSON,
    "BinaryField": FieldType.BINARY,
    "EmailField": FieldType.STRING,
    "URLField": FieldType.STRING,
    "SlugField": FieldType.STRING,
    "FileField": FieldType.STRING,
    "ImageField": FieldType.STRING,
}


class DjangoInspector(Inspector):
    def inspect(self, model_class: type, plural: str | None = None) -> ModelSchema:
        meta = model_class._meta
        fields: list[FieldSchema] = []

        for f in meta.get_fields():
            if f.many_to_many or f.one_to_many:
                continue

            field_type_name = type(f).__name__
            field_type = DJANGO_TYPE_MAP.get(field_type_name, FieldType.STRING)

            constraints = {}
            if hasattr(f, "max_length") and f.max_length:
                constraints["max_length"] = f.max_length

            relation = None
            if hasattr(f, "related_model") and f.related_model:
                relation = RelationSchema(
                    type="one_to_one" if f.one_to_one else "many_to_one",
                    target=f.related_model.__name__,
                )

            is_pk = getattr(f, "primary_key", False)
            required = not getattr(f, "blank", False) and not getattr(f, "null", False)
            default = f.default if hasattr(f, "default") and f.default is not None else None

            fields.append(FieldSchema(
                name=f.name,
                type=field_type,
                required=required and not is_pk,
                default=default,
                constraints=constraints,
                primary_key=is_pk,
                relation=relation,
            ))

        model_name = model_class.__name__
        plural_name = plural or pluralize(model_name)

        return ModelSchema(name=model_name, plural=plural_name, fields=fields)
