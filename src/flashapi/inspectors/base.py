from __future__ import annotations

from abc import ABC, abstractmethod

from flashapi.core.schema import ModelSchema


class Inspector(ABC):
    @abstractmethod
    def inspect(self, model_class: type, plural: str | None = None) -> ModelSchema:
        ...
