import pytest
from flashapi.features.search import apply_search


class TestSearch:
    def setup_method(self):
        self.items = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@test.org"},
            {"name": "Charlie", "email": "charlie@example.com"},
        ]
        self.fields = {"name", "email"}

    def test_search_by_name(self):
        result = apply_search(self.items, "alice", self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_search_case_insensitive(self):
        result = apply_search(self.items, "BOB", self.fields)
        assert len(result) == 1

    def test_search_by_email(self):
        result = apply_search(self.items, "example.com", self.fields)
        assert len(result) == 2

    def test_search_no_match(self):
        result = apply_search(self.items, "zzz", self.fields)
        assert len(result) == 0

    def test_search_none(self):
        result = apply_search(self.items, None, self.fields)
        assert len(result) == 3

    def test_search_empty_string(self):
        result = apply_search(self.items, "", self.fields)
        assert len(result) == 3

    def test_search_partial_match(self):
        result = apply_search(self.items, "li", self.fields)
        assert len(result) == 2  # Alice and Charlie
