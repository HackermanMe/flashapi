import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Product(BaseModel):
    name: str
    price: float


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Product], database=db_path)
    return TestClient(flash.app)


class TestExport:
    def test_export_csv(self, client):
        client.post("/api/products", json={"name": "Widget", "price": 9.99})
        client.post("/api/products", json={"name": "Gadget", "price": 19.99})

        resp = client.get("/api/products/export?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_export_unsupported_format(self, client):
        resp = client.get("/api/products/export?format=xml")
        assert resp.status_code == 400

    def test_export_empty(self, client):
        resp = client.get("/api/products/export?format=csv")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # header only
