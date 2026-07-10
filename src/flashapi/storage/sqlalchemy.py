from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from flashapi.storage.base import Storage


class SQLAlchemyStorage(Storage):
    """Storage backend that delegates to a SQLAlchemy session."""

    def __init__(self, session_factory, model_class: type):
        self._session_factory = session_factory
        self._model = model_class
        self._column_types = {
            col.name: col.type for col in model_class.__table__.columns
        }

    def _coerce_values(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert string values to proper Python types based on column definitions."""
        from sqlalchemy import Date, DateTime, Time, Boolean

        coerced = {}
        for key, value in data.items():
            if value is None:
                coerced[key] = None
                continue

            col_type = self._column_types.get(key)
            if col_type is None:
                coerced[key] = value
                continue

            if isinstance(col_type, DateTime) and isinstance(value, str):
                coerced[key] = datetime.fromisoformat(value)
            elif isinstance(col_type, Date) and isinstance(value, str):
                coerced[key] = date.fromisoformat(value)
            elif isinstance(col_type, Time) and isinstance(value, str):
                coerced[key] = time.fromisoformat(value)
            elif isinstance(col_type, Boolean) and not isinstance(value, bool):
                coerced[key] = bool(value)
            else:
                coerced[key] = value

        return coerced

    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        session = self._session_factory()
        try:
            instance = self._model(**self._coerce_values(data))
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return self._to_dict(instance)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, table: str, item_id: int | str) -> dict[str, Any] | None:
        session = self._session_factory()
        try:
            instance = session.get(self._model, item_id)
            if instance is None:
                return None
            return self._to_dict(instance)
        finally:
            session.close()

    def list_all(self, table: str) -> list[dict[str, Any]]:
        session = self._session_factory()
        try:
            instances = session.query(self._model).all()
            return [self._to_dict(obj) for obj in instances]
        finally:
            session.close()

    def update(self, table: str, item_id: int | str, data: dict[str, Any]) -> dict[str, Any] | None:
        session = self._session_factory()
        try:
            instance = session.get(self._model, item_id)
            if instance is None:
                return None
            for key, value in self._coerce_values(data).items():
                setattr(instance, key, value)
            session.commit()
            session.refresh(instance)
            return self._to_dict(instance)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, table: str, item_id: int | str) -> bool:
        session = self._session_factory()
        try:
            instance = session.get(self._model, item_id)
            if instance is None:
                return False
            session.delete(instance)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _to_dict(self, instance) -> dict[str, Any]:
        data = {}
        for col in instance.__table__.columns:
            value = getattr(instance, col.name, None)
            data[col.name] = self._serialize_value(value)
        return data

    def _serialize_value(self, value) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        import uuid as uuid_mod

        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, time):
            return value.isoformat()
        if isinstance(value, uuid_mod.UUID):
            return str(value)
        return str(value)
