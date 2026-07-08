import pytest
from dataclasses import dataclass

from flask import Flask
from flashapi import Model
from flashapi.flask import register_models


@dataclass
class User:
    name: str
    email: str


@dataclass
class Article:
    title: str
    content: str


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = Flask(__name__)
    register_models(app, models=[User, Model(Article, readonly=True)], database=db_path)
    app.testing = True
    return app.test_client()


class TestFlaskAdapter:
    def test_list_empty(self, client):
        resp = client.get("/users")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_create(self, client):
        resp = client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        assert resp.status_code == 201
        assert resp.get_json()["data"]["name"] == "Alice"

    def test_get_by_id(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.get("/users/1")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == "a@b.com"

    def test_get_404(self, client):
        resp = client.get("/users/999")
        assert resp.status_code == 404

    def test_update(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.put("/users/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated"

    def test_delete(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.delete("/users/1")
        assert resp.status_code == 204

    def test_pagination(self, client):
        for i in range(5):
            client.post("/users", json={"name": f"U{i}", "email": f"u{i}@t.com"})
        resp = client.get("/users?page=1&page_size=2")
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["total"] == 5

    def test_search(self, client):
        client.post("/users", json={"name": "Alice", "email": "a@t.com"})
        client.post("/users", json={"name": "Bob", "email": "b@t.com"})
        resp = client.get("/users?search=alice")
        assert len(resp.get_json()["data"]) == 1

    def test_readonly_blocked(self, client):
        resp = client.post("/articles", json={"title": "X", "content": "Y"})
        assert resp.status_code == 405

    def test_docs_endpoint(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert b"swagger-ui" in resp.data

    def test_openapi_json(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.get_json()
        assert spec["openapi"] == "3.1.0"
        assert "/users" in spec["paths"]
