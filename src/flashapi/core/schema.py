from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    UUID = "uuid"
    JSON = "json"
    TEXT = "text"
    BINARY = "binary"


@dataclass
class RelationSchema:
    type: str  # "one_to_one", "many_to_one", "one_to_many", "many_to_many"
    target: str
    target_plural: str = ""
    foreign_key: str = ""


@dataclass
class FieldSchema:
    name: str
    type: FieldType
    required: bool = True
    default: Any = None
    constraints: dict = field(default_factory=dict)
    primary_key: bool = False
    auto_generated: bool = False
    relation: RelationSchema | None = None
    readonly: bool = False
    writeonly: bool = False
    hidden: bool = False
    export_exclude: bool = False
    auto: str | None = None  # "uuid", "datetime", "date" — server-generated on create


@dataclass
class ModelSchema:
    name: str
    plural: str
    fields: list[FieldSchema]
    permissions: list[str] = field(
        default_factory=lambda: ["list", "read", "create", "update", "delete"],
    )
    soft_delete: bool = False
    audit: bool = False
    lookup_field: str = "id"
    access: str | dict | bool | None = None
    scope: str | None = None  # "tenant", "owner", or "both"
    tenant_field: str | None = None
    owner_field: str | None = None


ALL_OPERATIONS = ["list", "read", "create", "update", "delete"]

SOFT_DELETE_FIELD = "deleted_at"


class FlashAPIConfigError(Exception):
    pass


def validate_soft_delete(model_class: type, soft_delete: bool) -> None:
    """Raise if soft_delete=True but the model has no deleted_at field."""
    if not soft_delete:
        return

    if hasattr(model_class, "_meta"):
        try:
            model_class._meta.get_field(SOFT_DELETE_FIELD)
        except Exception:
            msg = (
                f'Model "{model_class.__name__}" has soft_delete=True but no '
                f"'{SOFT_DELETE_FIELD}' field. Add:\n"
                f"    {SOFT_DELETE_FIELD} = models.DateTimeField(null=True, blank=True)"
            )
            raise FlashAPIConfigError(
                msg,
            )
    elif hasattr(model_class, "__table__"):
        columns = {col.name for col in model_class.__table__.columns}
        if SOFT_DELETE_FIELD not in columns:
            msg = (
                f'Model "{model_class.__name__}" has soft_delete=True but no '
                f"'{SOFT_DELETE_FIELD}' column. Add:\n"
                f"    {SOFT_DELETE_FIELD} = Column(DateTime, nullable=True)"
            )
            raise FlashAPIConfigError(
                msg,
            )


class Model:
    """Wrapper to configure how a model is exposed via FlashAPI."""

    def __init__(
        self,
        model_class: type,
        *,
        readonly: bool = False,
        exclude: list[str] | None = None,
        only: list[str] | None = None,
        plural: str | None = None,
        soft_delete: bool = False,
        audit: bool = False,
        lookup_field: str = "id",
        access: str | dict | bool | None = None,
        scope: str | None = None,
        tenant_field: str | None = None,
        owner_field: str | None = None,
    ) -> None:
        self.model_class = model_class
        self.plural = plural
        self.soft_delete = soft_delete
        self.audit = audit
        self.lookup_field = lookup_field
        self.access = access
        self.scope = scope
        self.tenant_field = tenant_field
        self.owner_field = owner_field
        self.permissions = self._resolve_permissions(readonly, exclude, only)

    def _resolve_permissions(
        self,
        readonly: bool,
        exclude: list[str] | None,
        only: list[str] | None,
    ) -> list[str]:
        if only:
            return [op for op in only if op in ALL_OPERATIONS]
        if readonly:
            return ["list", "read"]
        if exclude:
            return [op for op in ALL_OPERATIONS if op not in exclude]
        return list(ALL_OPERATIONS)
