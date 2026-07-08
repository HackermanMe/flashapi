import pytest
from dataclasses import dataclass
from pydantic import BaseModel

from flashapi.inspectors.detect import inspect_model


class TestDetection:
    def test_detects_pydantic(self):
        class User(BaseModel):
            name: str

        schema = inspect_model(User)
        assert schema.name == "User"

    def test_detects_dataclass(self):
        @dataclass
        class Item:
            title: str

        schema = inspect_model(Item)
        assert schema.name == "Item"

    def test_rejects_plain_class(self):
        class Plain:
            pass

        with pytest.raises(TypeError, match="Unsupported model type"):
            inspect_model(Plain)

    def test_custom_plural_passed_through(self):
        @dataclass
        class Mouse:
            name: str

        schema = inspect_model(Mouse, plural="mice")
        assert schema.plural == "mice"
