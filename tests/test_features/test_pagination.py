from flashapi.features.pagination import paginate


class TestPaginate:
    def setup_method(self):
        self.items = [{"id": i} for i in range(50)]

    def test_first_page(self):
        result, total = paginate(self.items, page=0, size=10)
        assert len(result) == 10
        assert total == 50
        assert result[0]["id"] == 0

    def test_second_page(self):
        result, total = paginate(self.items, page=1, size=10)
        assert len(result) == 10
        assert result[0]["id"] == 10

    def test_last_page_partial(self):
        result, total = paginate(self.items, page=5, size=10)
        assert len(result) == 0

    def test_page_beyond_range(self):
        result, total = paginate(self.items, page=100, size=10)
        assert len(result) == 0
        assert total == 50

    def test_size_capped_at_100(self):
        result, total = paginate(self.items, page=0, size=200)
        assert len(result) == 50

    def test_size_minimum_1(self):
        result, total = paginate(self.items, page=0, size=0)
        assert len(result) == 1

    def test_page_minimum_0(self):
        result, total = paginate(self.items, page=-5, size=10)
        assert len(result) == 10
        assert result[0]["id"] == 0

    def test_empty_list(self):
        result, total = paginate([], page=0, size=10)
        assert result == []
        assert total == 0
