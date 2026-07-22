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

    def _get_instance(self, item_id, lookup_field="id"):
        try:
            if lookup_field == "id":
                return self._model.objects.get(pk=item_id)
            return self._model.objects.get(**{lookup_field: item_id})
        except self._model.DoesNotExist:
            return None

    def get(self, table: str, item_id: int | str, *, lookup_field: str = "id") -> dict[str, Any] | None:
        instance = self._get_instance(item_id, lookup_field)
        if instance is None:
            return None
        return self._to_dict(instance)

    def list_all(self, table: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        return [self._to_dict(obj) for obj in self._model.objects.all()]

    def update(self, table: str, item_id: int | str, data: dict[str, Any], *, lookup_field: str = "id") -> dict[str, Any] | None:
        instance = self._get_instance(item_id, lookup_field)
        if instance is None:
            return None

        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        return self._to_dict(instance)

    def delete(self, table: str, item_id: int | str, *, soft: bool = True, lookup_field: str = "id") -> bool:
        instance = self._get_instance(item_id, lookup_field)
        if instance is None:
            return False
        instance.delete()
        return True

    def restore(self, table: str, item_id: int | str, *, lookup_field: str = "id") -> bool:
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
