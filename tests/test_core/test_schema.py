import pytest
from flashapi.core.schema import Model, ALL_OPERATIONS


class TestModel:
    def test_default_permissions(self):
        m = Model(object)
        assert m.permissions == ALL_OPERATIONS

    def test_readonly(self):
        m = Model(object, readonly=True)
        assert m.permissions == ["list", "read"]

    def test_exclude(self):
        m = Model(object, exclude=["delete", "update"])
        assert "delete" not in m.permissions
        assert "update" not in m.permissions
        assert "list" in m.permissions
        assert "read" in m.permissions
        assert "create" in m.permissions

    def test_only(self):
        m = Model(object, only=["list"])
        assert m.permissions == ["list"]

    def test_only_takes_precedence_over_readonly(self):
        m = Model(object, readonly=True, only=["create"])
        assert m.permissions == ["create"]

    def test_custom_plural(self):
        m = Model(object, plural="custom_items")
        assert m.plural == "custom_items"

    def test_no_plural(self):
        m = Model(object)
        assert m.plural is None
