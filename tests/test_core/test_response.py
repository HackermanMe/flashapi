from flashapi.core.response import (
    default_formatter,
    create_list_response,
    create_item_response,
)


class TestDefaultFormatter:
    def test_list_data(self):
        result = default_formatter([{"id": 1}], {"total": 1})
        assert result == {"data": [{"id": 1}], "total": 1}

    def test_single_item(self):
        result = default_formatter({"id": 1, "name": "test"})
        assert result == {"data": {"id": 1, "name": "test"}}

    def test_list_without_meta(self):
        result = default_formatter([{"id": 1}])
        assert result == {"data": [{"id": 1}]}


class TestCreateListResponse:
    def test_basic(self):
        result = create_list_response(
            data=[{"id": 1}],
            total=50,
            page=1,
            page_size=20,
        )
        assert result == {
            "data": [{"id": 1}],
            "total": 50,
            "page": 1,
            "pages": 3,
            "page_size": 20,
        }

    def test_pages_calculation(self):
        result = create_list_response([], total=0, page=1, page_size=20)
        assert result["pages"] == 0

    def test_pages_exact_division(self):
        result = create_list_response([], total=40, page=1, page_size=20)
        assert result["pages"] == 2

    def test_custom_formatter(self):
        def custom(data, meta):
            return {"results": data, "info": meta}

        result = create_list_response([{"id": 1}], total=1, page=1, page_size=10, formatter=custom)
        assert "results" in result
        assert "info" in result


class TestCreateItemResponse:
    def test_basic(self):
        result = create_item_response({"id": 1, "name": "Alice"})
        assert result == {"data": {"id": 1, "name": "Alice"}}

    def test_custom_formatter(self):
        def custom(data, meta):
            return {"item": data}

        result = create_item_response({"id": 1}, formatter=custom)
        assert result == {"item": {"id": 1}}
