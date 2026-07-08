import pytest
from pydantic import BaseModel

from flashapi.core.schema import FieldType
from flashapi.inspectors.pydantic import PydanticInspector


class TestPydanticInspector:
    def test_basic_model(self):
        class User(BaseModel):
            name: str
            age: int

        schema = PydanticInspector().inspect(User)
        assert schema.name == "User"
        assert schema.plural == "users"
        field_names = [f.name for f in schema.fields]
        assert "id" in field_names
        assert "name" in field_names
        assert "age" in field_names

    def test_field_types(self):
        class Item(BaseModel):
            title: str
            count: int
            price: float
            active: bool

        schema = PydanticInspector().inspect(Item)
        fields_by_name = {f.name: f for f in schema.fields}
        assert fields_by_name["title"].type == FieldType.STRING
        assert fields_by_name["count"].type == FieldType.INTEGER
        assert fields_by_name["price"].type == FieldType.FLOAT
        assert fields_by_name["active"].type == FieldType.BOOLEAN

    def test_optional_field(self):
        from typing import Optional

        class Profile(BaseModel):
            name: str
            bio: Optional[str] = None

        schema = PydanticInspector().inspect(Profile)
        fields_by_name = {f.name: f for f in schema.fields}
        assert fields_by_name["name"].required is True
        assert fields_by_name["bio"].required is False

    def test_custom_plural(self):
        class Category(BaseModel):
            name: str

        schema = PydanticInspector().inspect(Category, plural="categories")
        assert schema.plural == "categories"

    def test_auto_plural(self):
        class Category(BaseModel):
            name: str

        schema = PydanticInspector().inspect(Category)
        assert schema.plural == "categories"

    def test_auto_id_field(self):
        class Thing(BaseModel):
            value: str

        schema = PydanticInspector().inspect(Thing)
        id_field = next(f for f in schema.fields if f.name == "id")
        assert id_field.primary_key is True
        assert id_field.type == FieldType.INTEGER
