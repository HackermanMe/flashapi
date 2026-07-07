from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from flashapi.core.schema import ModelSchema


class Adapter(ABC):
    @abstractmethod
    def register_model(self, schema: ModelSchema, permissions: list[str], storage: Any) -> None:
        ...
