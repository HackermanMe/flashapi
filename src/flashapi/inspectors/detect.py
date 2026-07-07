from __future__ import annotations

from dataclasses import is_dataclass

from flashapi.core.schema import ModelSchema


def inspect_model(model_class: type, plural: str | None = None) -> ModelSchema:
    if _is_django_model(model_class):
        from flashapi.inspectors.django import DjangoInspector
        return DjangoInspector().inspect(model_class, plural)

    if _is_sqlalchemy_model(model_class):
        from flashapi.inspectors.sqlalchemy import SQLAlchemyInspector
        return SQLAlchemyInspector().inspect(model_class, plural)

    if _is_pydantic_model(model_class):
        from flashapi.inspectors.pydantic import PydanticInspector
        return PydanticInspector().inspect(model_class, plural)

    if is_dataclass(model_class):
        from flashapi.inspectors.dataclass import DataclassInspector
        return DataclassInspector().inspect(model_class, plural)

    raise TypeError(
        f"Unsupported model type: {model_class}. "
        "FlashAPI supports Django models, SQLAlchemy models, Pydantic models, and dataclasses."
    )


def _is_django_model(cls: type) -> bool:
    try:
        from django.db import models
        return issubclass(cls, models.Model)
    except ImportError:
        return False


def _is_sqlalchemy_model(cls: type) -> bool:
    return hasattr(cls, "__table__") and hasattr(cls, "__tablename__")


def _is_pydantic_model(cls: type) -> bool:
    try:
        from pydantic import BaseModel
        return issubclass(cls, BaseModel)
    except ImportError:
        return False
