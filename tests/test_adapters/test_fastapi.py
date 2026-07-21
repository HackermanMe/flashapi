import pytest
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
        resp = client.get("/api/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["totalElements"] == 0
        assert data["meta"]["page"] == 0
        assert data["meta"]["size"] == 20

    def test_create(self, client):
        resp = client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Alice"
        assert data["email"] == "a@b.com"
        assert "id" in data

    def test_get_by_id(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.get("/api/users/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Alice"

    def test_get_404(self, client):
        resp = client.get("/api/users/999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "Not found"
        assert data["status"] == 404

    def test_update(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.put("/api/users/1", json={"name": "Bob"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Bob"

    def test_update_404(self, client):
        resp = client.put("/api/users/999", json={"name": "X"})
        assert resp.status_code == 404
        assert resp.json()["status"] == 404

    def test_delete(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.delete("/api/users/1")
        assert resp.status_code == 204
        assert client.get("/api/users/1").status_code == 404

    def test_delete_404(self, client):
        resp = client.delete("/api/users/999")
        assert resp.status_code == 404

    def test_pagination(self, client):
        for i in range(5):
            client.post("/api/users", json={"name": f"User{i}", "email": f"u{i}@t.com"})
        resp = client.get("/api/users?page=0&size=2")
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["totalElements"] == 5
        assert data["meta"]["totalPages"] == 3

    def test_pagination_second_page(self, client):
        for i in range(5):
            client.post("/api/users", json={"name": f"User{i}", "email": f"u{i}@t.com"})
        resp = client.get("/api/users?page=1&size=2")
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "User2"

    def test_filtering(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        client.post("/api/users", json={"name": "Bob", "email": "b@b.com"})
        resp = client.get("/api/users?name=Bob")
        assert len(resp.json()["data"]) == 1

    def test_sorting(self, client):
        client.post("/api/users", json={"name": "Charlie", "email": "c@t.com"})
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com"})
        resp = client.get("/api/users?sort=name")
        names = [u["name"] for u in resp.json()["data"]]
        assert names == ["Alice", "Charlie"]

    def test_search(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "alice@test.com"})
        client.post("/api/users", json={"name": "Bob", "email": "bob@other.com"})
        resp = client.get("/api/users?search=alice")
        assert len(resp.json()["data"]) == 1

    def test_readonly_get(self, client):
        resp = client.get("/api/products")
        assert resp.status_code == 200

    def test_readonly_post_blocked(self, client):
        resp = client.post("/api/products", json={"title": "X", "price": 10})
        assert resp.status_code == 405

    def test_readonly_delete_blocked(self, client):
        resp = client.delete("/api/products/1")
        assert resp.status_code == 405
