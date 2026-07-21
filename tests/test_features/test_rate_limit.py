import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Item(BaseModel):
    name: str


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Item], database=db_path, rate_limit=5, rate_window=60)
    return TestClient(flash.app)


class TestRateLimiting:
    def test_headers_present(self, client):
        resp = client.get("/api/items")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-reset" in resp.headers
        assert resp.headers["x-ratelimit-limit"] == "5"

    def test_rate_limit_exceeded(self, client):
        for _ in range(5):
            resp = client.get("/api/items")
            assert resp.status_code == 200

        resp = client.get("/api/items")
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"] == "Rate limit exceeded"
        assert data["status"] == 429
        assert "retryAfter" in data

    def test_remaining_decreases(self, client):
        resp1 = client.get("/api/items")
        remaining1 = int(resp1.headers["x-ratelimit-remaining"])

        resp2 = client.get("/api/items")
        remaining2 = int(resp2.headers["x-ratelimit-remaining"])

        assert remaining2 < remaining1
