import pytest
from flashapi.features.sorting import apply_sorting


class TestSorting:
    def setup_method(self):
        self.items = [
            {"name": "Charlie", "age": 35},
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        self.fields = {"name", "age"}

    def test_sort_ascending(self):
        result = apply_sorting(self.items, "name", self.fields)
        assert [r["name"] for r in result] == ["Alice", "Bob", "Charlie"]

    def test_sort_descending(self):
        result = apply_sorting(self.items, "-name", self.fields)
        assert [r["name"] for r in result] == ["Charlie", "Bob", "Alice"]

    def test_sort_by_number(self):
        result = apply_sorting(self.items, "age", self.fields)
        assert [r["age"] for r in result] == [25, 30, 35]

    def test_sort_none(self):
        result = apply_sorting(self.items, None, self.fields)
        assert result == self.items

    def test_sort_invalid_field(self):
        result = apply_sorting(self.items, "unknown", self.fields)
        assert result == self.items

    def test_empty_list(self):
        result = apply_sorting([], "name", self.fields)
        assert result == []
