import pytest
from dataclasses import dataclass

from flashapi.core.schema import FieldType
from flashapi.inspectors.dataclass import DataclassInspector


class TestDataclassInspector:
    def test_basic(self):
        @dataclass
        class Book:
            title: str
            pages: int

        schema = DataclassInspector().inspect(Book)
        assert schema.name == "Book"
        assert schema.plural == "books"
        field_names = [f.name for f in schema.fields]
        assert "id" in field_names
        assert "title" in field_names
        assert "pages" in field_names

    def test_field_types(self):
        @dataclass
        class Item:
            name: str
            count: int
            price: float
            active: bool

        schema = DataclassInspector().inspect(Item)
        fields_by_name = {f.name: f for f in schema.fields}
        assert fields_by_name["name"].type == FieldType.STRING
        assert fields_by_name["count"].type == FieldType.INTEGER
        assert fields_by_name["price"].type == FieldType.FLOAT
        assert fields_by_name["active"].type == FieldType.BOOLEAN

    def test_default_values(self):
        @dataclass
        class Config:
            name: str
            debug: bool = False

        schema = DataclassInspector().inspect(Config)
        fields_by_name = {f.name: f for f in schema.fields}
        assert fields_by_name["name"].required is True
        assert fields_by_name["debug"].required is False
        assert fields_by_name["debug"].default is False

    def test_custom_plural(self):
        @dataclass
        class Person:
            name: str

        schema = DataclassInspector().inspect(Person, plural="people")
        assert schema.plural == "people"

    def test_auto_plural(self):
        @dataclass
        class Person:
            name: str

        schema = DataclassInspector().inspect(Person)
        assert schema.plural == "people"
