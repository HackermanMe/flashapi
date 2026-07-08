import pytest
import os
from pydantic import BaseModel

from flashapi import Model
from flashapi.fastapi import FlashAPI


class User(BaseModel):
    name: str
    email: str


class Product(BaseModel):
    title: str
    price: float


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[User, Model(Product, readonly=True)], database=db_path)
    return TestClient(flash.app)


class TestFastAPIAdapter:
    def test_list_empty(self, client):
        resp = client.get("/users")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["total"] == 0

    def test_create(self, client):
        resp = client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Alice"
        assert data["email"] == "a@b.com"
        assert "id" in data

    def test_get_by_id(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.get("/users/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Alice"

    def test_get_404(self, client):
        resp = client.get("/users/999")
        assert resp.status_code == 404

    def test_update(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.put("/users/1", json={"name": "Bob"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Bob"

    def test_update_404(self, client):
        resp = client.put("/users/999", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.delete("/users/1")
        assert resp.status_code == 204
        assert client.get("/users/1").status_code == 404

    def test_delete_404(self, client):
        resp = client.delete("/users/999")
        assert resp.status_code == 404

    def test_pagination(self, client):
        for i in range(5):
            client.post("/users", json={"name": f"User{i}", "email": f"u{i}@t.com"})
        resp = client.get("/users?page=1&page_size=2")
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    def test_filtering(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        client.post("/users", json={"name": "Bob", "email": "b@b.com"})
        resp = client.get("/users?name=Bob")
        assert len(resp.json()["data"]) == 1

    def test_sorting(self, client):
        client.post("/users", json={"name": "Charlie", "email": "c@t.com"})
        client.post("/users", json={"name": "Alice", "email": "a@t.com"})
        resp = client.get("/users?sort=name")
        names = [u["name"] for u in resp.json()["data"]]
        assert names == ["Alice", "Charlie"]

    def test_search(self, client):
        client.post("/users", json={"name": "Alice", "email": "alice@test.com"})
        client.post("/users", json={"name": "Bob", "email": "bob@other.com"})
        resp = client.get("/users?search=alice")
        assert len(resp.json()["data"]) == 1

    def test_readonly_get(self, client):
        resp = client.get("/products")
        assert resp.status_code == 200

    def test_readonly_post_blocked(self, client):
        resp = client.post("/products", json={"title": "X", "price": 10})
        assert resp.status_code == 405

    def test_readonly_delete_blocked(self, client):
        resp = client.delete("/products/1")
        assert resp.status_code == 405
