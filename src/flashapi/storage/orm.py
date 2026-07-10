from __future__ import annotations

from typing import Any

from flashapi.storage.base import Storage


class DjangoORMStorage(Storage):
    """Storage backend that delegates to Django's ORM."""

    def __init__(self, model_class: type):
        self._model = model_class

    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        instance = self._model.objects.create(**data)
        return self._to_dict(instance)

    def get(self, table: str, item_id: int | str) -> dict[str, Any] | None:
        try:
            instance = self._model.objects.get(pk=item_id)
            return self._to_dict(instance)
        except self._model.DoesNotExist:
            return None

    def list_all(self, table: str) -> list[dict[str, Any]]:
        return [self._to_dict(obj) for obj in self._model.objects.all()]

    def update(self, table: str, item_id: int | str, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            instance = self._model.objects.get(pk=item_id)
        except self._model.DoesNotExist:
            return None

        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        return self._to_dict(instance)

    def delete(self, table: str, item_id: int | str) -> bool:
        try:
            instance = self._model.objects.get(pk=item_id)
            instance.delete()
            return True
        except self._model.DoesNotExist:
            return False

    def _to_dict(self, instance) -> dict[str, Any]:

        data = {}
        for field in instance._meta.get_fields():
            if field.many_to_many or field.one_to_many:
                continue
            if hasattr(field, "related_model") and field.related_model:
                name = field.attname
            else:
                name = field.name
            value = getattr(instance, name, None)
            data[name] = self._serialize_value(value)
        return data

    def _serialize_value(self, value) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        import uuid

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
        if isinstance(value, uuid.UUID):
            return str(value)
        if hasattr(value, "field") and hasattr(value, "name"):
            try:
                return value.name or None
            except (ValueError, AttributeError):
                return None
        return str(value)
