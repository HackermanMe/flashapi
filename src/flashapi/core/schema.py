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


@dataclass
class ModelSchema:
    name: str
    plural: str
    fields: list[FieldSchema]
    permissions: list[str] = field(
        default_factory=lambda: ["list", "read", "create", "update", "delete"]
    )


ALL_OPERATIONS = ["list", "read", "create", "update", "delete"]


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
    ):
        self.model_class = model_class
        self.plural = plural
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
