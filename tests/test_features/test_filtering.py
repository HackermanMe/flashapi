import pytest
from flashapi.features.filtering import apply_filters


class TestFiltering:
    def setup_method(self):
        self.items = [
            {"name": "Alice", "age": 30, "city": "Paris"},
            {"name": "Bob", "age": 25, "city": "Lyon"},
            {"name": "Charlie", "age": 30, "city": "Paris"},
        ]
        self.fields = {"name", "age", "city"}

    def test_single_filter(self):
        result = apply_filters(self.items, {"name": "Alice"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_multiple_filters(self):
        result = apply_filters(self.items, {"age": "30", "city": "Paris"}, self.fields)
        assert len(result) == 2

    def test_no_match(self):
        result = apply_filters(self.items, {"name": "Nobody"}, self.fields)
        assert len(result) == 0

    def test_empty_filters(self):
        result = apply_filters(self.items, {}, self.fields)
        assert len(result) == 3

    def test_reserved_params_ignored(self):
        result = apply_filters(self.items, {"page": "1", "sort": "name"}, self.fields)
        assert len(result) == 3

    def test_unknown_field_ignored(self):
        result = apply_filters(self.items, {"unknown": "value"}, self.fields)
        assert len(result) == 3

    def test_integer_filter_as_string(self):
        result = apply_filters(self.items, {"age": "25"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"
