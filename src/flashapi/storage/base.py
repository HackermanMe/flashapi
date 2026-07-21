from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Storage(ABC):
    @abstractmethod
    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def get(self, table: str, item_id: int | str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def list_all(self, table: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def update(self, table: str, item_id: int | str, data: dict[str, Any]) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def delete(self, table: str, item_id: int | str, *, soft: bool = True) -> bool:
        ...

    def restore(self, table: str, item_id: int | str) -> bool:
        return False

    def bulk_create(self, table: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.create(table, item) for item in items]
