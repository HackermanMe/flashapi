"""Test field selection (?fields=id,name) feature."""
import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Product(BaseModel):
    name: str
    price: float
    category: str
    stock: int = 0


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Product], database=db_path)
    return TestClient(flash.app)


@pytest.fixture
def seeded_client(client):
    """Client with seeded data."""
    client.post("/api/products", json={"name": "Laptop", "price": 999.99, "category": "Electronics", "stock": 10})
    client.post("/api/products", json={"name": "Mouse", "price": 29.99, "category": "Electronics", "stock": 50})
    return client


class TestFieldSelection:
    """Test ?fields parameter for field selection."""

    def test_list_all_fields_by_default(self, seeded_client):
        """Without ?fields, return all fields."""
        resp = seeded_client.get("/api/products")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert set(data[0].keys()) == {"id", "name", "price", "category", "stock"}

    def test_list_select_single_field(self, seeded_client):
        """?fields=name returns only name (and id)."""
        resp = seeded_client.get("/api/products?fields=name")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # id is always included
        assert set(data[0].keys()) == {"id", "name"}
        assert "price" not in data[0]
        assert "category" not in data[0]

    def test_list_select_multiple_fields(self, seeded_client):
        """?fields=name,price returns name and price (and id)."""
        resp = seeded_client.get("/api/products?fields=name,price")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert set(data[0].keys()) == {"id", "name", "price"}
        assert "category" not in data[0]
        assert "stock" not in data[0]

    def test_list_select_with_spaces(self, seeded_client):
        """?fields=name, price handles spaces correctly."""
        resp = seeded_client.get("/api/products?fields=name,%20price")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data[0].keys()) == {"id", "name", "price"}

    def test_get_all_fields_by_default(self, seeded_client):
        """GET /{id} without ?fields returns all fields."""
        resp = seeded_client.get("/api/products/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data.keys()) == {"id", "name", "price", "category", "stock"}

    def test_get_select_single_field(self, seeded_client):
        """GET /{id}?fields=name returns only name (and id)."""
        resp = seeded_client.get("/api/products/1?fields=name")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data.keys()) == {"id", "name"}
        assert data["name"] == "Laptop"

    def test_get_select_multiple_fields(self, seeded_client):
        """GET /{id}?fields=name,price returns name and price."""
        resp = seeded_client.get("/api/products/1?fields=name,price")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data.keys()) == {"id", "name", "price"}
        assert data["name"] == "Laptop"
        assert data["price"] == 999.99

    def test_select_nonexistent_field_ignored(self, seeded_client):
        """?fields=name,invalid ignores invalid field."""
        resp = seeded_client.get("/api/products?fields=name,invalid")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Only name is returned (invalid ignored)
        assert set(data[0].keys()) == {"id", "name"}

    def test_fields_with_pagination(self, seeded_client):
        """?fields works with pagination."""
        resp = seeded_client.get("/api/products?fields=name&page=0&size=1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert set(data[0].keys()) == {"id", "name"}

    def test_fields_with_filter(self, seeded_client):
        """?fields works with filtering."""
        resp = seeded_client.get("/api/products?fields=name,price&category.eq=Electronics")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert set(data[0].keys()) == {"id", "name", "price"}

    def test_fields_with_sorting(self, seeded_client):
        """?fields works with sorting."""
        resp = seeded_client.get("/api/products?fields=name&sort=name,asc")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["name"] == "Laptop"
        assert data[1]["name"] == "Mouse"
        assert "price" not in data[0]
