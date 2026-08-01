import pytest
from flashapi.features.filtering import apply_filters, _parse_filter_key


class TestParseFilterKey:
    def test_simple_field(self):
        assert _parse_filter_key("name") == ("name", "eq")

    def test_field_with_operator(self):
        assert _parse_filter_key("price.gte") == ("price", "gte")

    def test_field_with_dot_not_operator(self):
        assert _parse_filter_key("user.name") == ("user.name", "eq")

    def test_all_operators(self):
        ops = ["eq", "neq", "gt", "gte", "lt", "lte",
               "contains", "startswith", "endswith", "isnull", "in"]
        for op in ops:
            assert _parse_filter_key(f"field.{op}") == ("field", op)


class TestFiltering:
    def setup_method(self):
        self.items = [
            {"name": "Alice", "age": 30, "city": "Paris", "email": "alice@test.com"},
            {"name": "Bob", "age": 25, "city": "Lyon", "email": "bob@test.com"},
            {"name": "Charlie", "age": 35, "city": "Paris", "email": None},
        ]
        self.fields = {"name", "age", "city", "email"}

    def test_exact_match(self):
        result = apply_filters(self.items, {"name": "Alice"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_eq_operator(self):
        result = apply_filters(self.items, {"name.eq": "Bob"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"

    def test_neq_operator(self):
        result = apply_filters(self.items, {"city.neq": "Paris"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"

    def test_gt_operator(self):
        result = apply_filters(self.items, {"age.gt": "30"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Charlie"

    def test_gte_operator(self):
        result = apply_filters(self.items, {"age.gte": "30"}, self.fields)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"Alice", "Charlie"}

    def test_lt_operator(self):
        result = apply_filters(self.items, {"age.lt": "30"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"

    def test_lte_operator(self):
        result = apply_filters(self.items, {"age.lte": "30"}, self.fields)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"Alice", "Bob"}

    def test_contains_operator(self):
        result = apply_filters(self.items, {"name.contains": "li"}, self.fields)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"Alice", "Charlie"}

    def test_contains_case_insensitive(self):
        result = apply_filters(self.items, {"name.contains": "LI"}, self.fields)
        assert len(result) == 2

    def test_startswith_operator(self):
        result = apply_filters(self.items, {"name.startswith": "Al"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_startswith_case_insensitive(self):
        result = apply_filters(self.items, {"name.startswith": "al"}, self.fields)
        assert len(result) == 1

    def test_endswith_operator(self):
        result = apply_filters(self.items, {"name.endswith": "lie"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Charlie"

    def test_isnull_true(self):
        result = apply_filters(self.items, {"email.isnull": "true"}, self.fields)
        assert len(result) == 1
        assert result[0]["name"] == "Charlie"

    def test_isnull_false(self):
        result = apply_filters(self.items, {"email.isnull": "false"}, self.fields)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"Alice", "Bob"}

    def test_in_operator(self):
        result = apply_filters(self.items, {"city.in": "Paris,Lyon"}, self.fields)
        assert len(result) == 3

    def test_in_operator_subset(self):
        result = apply_filters(self.items, {"name.in": "Alice,Bob"}, self.fields)
        assert len(result) == 2

    def test_multiple_filters(self):
        result = apply_filters(self.items, {"age.gte": "30", "city": "Paris"}, self.fields)
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

    def test_comparison_on_none_returns_no_match(self):
        result = apply_filters(self.items, {"email.gt": "a"}, self.fields)
        assert all(r["email"] is not None for r in result)
