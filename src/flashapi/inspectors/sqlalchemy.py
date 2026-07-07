from __future__ import annotations

from flashapi.core.schema import FieldSchema, FieldType, ModelSchema, RelationSchema
from flashapi.core.pluralize import pluralize
from flashapi.inspectors.base import Inspector


def _map_sa_type(col_type) -> FieldType:
    type_name = type(col_type).__name__.upper()
    mapping = {
        "VARCHAR": FieldType.STRING,
        "STRING": FieldType.STRING,
        "TEXT": FieldType.TEXT,
        "INTEGER": FieldType.INTEGER,
        "BIGINTEGER": FieldType.INTEGER,
        "SMALLINTEGER": FieldType.INTEGER,
        "FLOAT": FieldType.FLOAT,
        "NUMERIC": FieldType.FLOAT,
        "BOOLEAN": FieldType.BOOLEAN,
        "DATE": FieldType.DATE,
        "DATETIME": FieldType.DATETIME,
        "TIME": FieldType.TIME,
        "UUID": FieldType.UUID,
        "JSON": FieldType.JSON,
        "BLOB": FieldType.BINARY,
        "LARGEBINARY": FieldType.BINARY,
    }
    return mapping.get(type_name, FieldType.STRING)


class SQLAlchemyInspector(Inspector):
    def inspect(self, model_class: type, plural: str | None = None) -> ModelSchema:
        table = model_class.__table__
        fields: list[FieldSchema] = []

        for col in table.columns:
            field_type = _map_sa_type(col.type)
            constraints = {}

            if hasattr(col.type, "length") and col.type.length:
                constraints["max_length"] = col.type.length

            relation = None
            if col.foreign_keys:
                fk = next(iter(col.foreign_keys))
                target_table = fk.column.table.name
                relation = RelationSchema(type="many_to_one", target=target_table)

            fields.append(FieldSchema(
                name=col.name,
                type=field_type,
                required=not col.nullable and not col.primary_key,
                default=col.default.arg if col.default and callable(col.default.arg) is False else None,
                constraints=constraints,
                primary_key=col.primary_key,
                relation=relation,
            ))

        model_name = model_class.__name__
        plural_name = plural or pluralize(model_name)

        return ModelSchema(name=model_name, plural=plural_name, fields=fields)
