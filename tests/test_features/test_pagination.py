import pytest
from flashapi.features.pagination import paginate


class TestPaginate:
    def setup_method(self):
        self.items = [{"id": i} for i in range(50)]

    def test_first_page(self):
        result, total = paginate(self.items, page=1, page_size=10)
        assert len(result) == 10
        assert total == 50
        assert result[0]["id"] == 0

    def test_second_page(self):
        result, total = paginate(self.items, page=2, page_size=10)
        assert len(result) == 10
        assert result[0]["id"] == 10

    def test_last_page_partial(self):
        result, total = paginate(self.items, page=6, page_size=10)
        assert len(result) == 0

    def test_page_beyond_range(self):
        result, total = paginate(self.items, page=100, page_size=10)
        assert len(result) == 0
        assert total == 50

    def test_page_size_capped_at_100(self):
        result, total = paginate(self.items, page=1, page_size=200)
        assert len(result) == 50

    def test_page_size_minimum_1(self):
        result, total = paginate(self.items, page=1, page_size=0)
        assert len(result) == 1

    def test_page_minimum_1(self):
        result, total = paginate(self.items, page=-5, page_size=10)
        assert len(result) == 10
        assert result[0]["id"] == 0

    def test_empty_list(self):
        result, total = paginate([], page=1, page_size=10)
        assert result == []
        assert total == 0
