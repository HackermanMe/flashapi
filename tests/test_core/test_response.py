from flashapi.core.response import (
    create_list_response,
    create_item_response,
    create_error_response,
)


class TestCreateListResponse:
    def test_basic(self):
        result = create_list_response(
            data=[{"id": 1}],
            total=50,
            page=0,
            size=20,
        )
        assert result == {
            "data": [{"id": 1}],
            "meta": {
                "page": 0,
                "size": 20,
                "totalElements": 50,
                "totalPages": 3,
            },
        }

    def test_page_zero_indexed(self):
        result = create_list_response([], total=0, page=0, size=20)
        assert result["meta"]["page"] == 0
        assert result["meta"]["totalPages"] == 0

    def test_pages_exact_division(self):
        result = create_list_response([], total=40, page=0, size=20)
        assert result["meta"]["totalPages"] == 2

    def test_pages_remainder(self):
        result = create_list_response([], total=41, page=0, size=20)
        assert result["meta"]["totalPages"] == 3

    def test_custom_formatter(self):
        def custom(response):
            response["custom"] = True
            return response

        result = create_list_response([{"id": 1}], total=1, page=0, size=10, formatter=custom)
        assert result["custom"] is True
        assert "data" in result
        assert "meta" in result


class TestCreateItemResponse:
    def test_basic(self):
        result = create_item_response({"id": 1, "name": "Alice"})
        assert result == {"data": {"id": 1, "name": "Alice"}}

    def test_custom_formatter(self):
        def custom(response):
            response["wrapped"] = True
            return response

        result = create_item_response({"id": 1}, formatter=custom)
        assert result["wrapped"] is True
        assert result["data"] == {"id": 1}


class TestCreateErrorResponse:
    def test_basic(self):
        result = create_error_response("Not found", 404)
        assert result == {"error": "Not found", "status": 404}

    def test_400(self):
        result = create_error_response("Bad request", 400)
        assert result == {"error": "Bad request", "status": 400}
