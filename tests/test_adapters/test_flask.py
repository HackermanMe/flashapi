import pytest
from dataclasses import dataclass

from flask import Flask
from flashapi import Model
from flashapi.flask import register_models


@dataclass
class User:
    name: str
    email: str
    age: int = 0


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
        resp = client.get("/api/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["meta"]["page"] == 0
        assert data["meta"]["size"] == 20
        assert data["meta"]["totalElements"] == 0
        assert data["meta"]["totalPages"] == 0

    def test_create(self, client):
        resp = client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        assert resp.status_code == 201
        assert resp.get_json()["data"]["name"] == "Alice"

    def test_get_by_id(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.get("/api/users/1")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == "a@b.com"

    def test_get_404(self, client):
        resp = client.get("/api/users/999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "Not found"
        assert data["status"] == 404

    def test_update(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.put("/api/users/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated"

    def test_delete(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@b.com"})
        resp = client.delete("/api/users/1")
        assert resp.status_code == 204

    def test_pagination(self, client):
        for i in range(5):
            client.post("/api/users", json={"name": f"U{i}", "email": f"u{i}@t.com"})
        resp = client.get("/api/users?page=0&size=2")
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["meta"]["totalElements"] == 5
        assert data["meta"]["totalPages"] == 3

    def test_pagination_page_1(self, client):
        for i in range(5):
            client.post("/api/users", json={"name": f"U{i}", "email": f"u{i}@t.com"})
        resp = client.get("/api/users?page=1&size=2")
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "U2"

    def test_search(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com"})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com"})
        resp = client.get("/api/users?search=alice")
        assert len(resp.get_json()["data"]) == 1

    def test_filter(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com"})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com"})
        resp = client.get("/api/users?name=Bob")
        assert len(resp.get_json()["data"]) == 1
        assert resp.get_json()["data"][0]["name"] == "Bob"

    def test_readonly_blocked(self, client):
        resp = client.post("/api/articles", json={"title": "X", "content": "Y"})
        assert resp.status_code == 405

    def test_docs_endpoint(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        assert b"swagger-ui" in resp.data

    def test_openapi_json(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        spec = resp.get_json()
        assert spec["openapi"] == "3.1.0"

    # --- Advanced filters ---

    def test_filter_gt(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?age.gt=28")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_filter_gte(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?age.gte=30")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_filter_lt(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?age.lt=30")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Bob"

    def test_filter_contains(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?name.contains=lic")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_filter_startswith(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?name.startswith=Bo")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Bob"

    def test_filter_in(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        client.post("/api/users", json={"name": "Charlie", "email": "c@t.com", "age": 35})
        resp = client.get("/api/users?name.in=Alice,Charlie")
        data = resp.get_json()["data"]
        assert len(data) == 2

    def test_filter_neq(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.get("/api/users?name.neq=Alice")
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Bob"

    # --- Bulk update ---

    def test_bulk_update(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.put("/api/users/bulk", json=[
            {"id": 1, "name": "Alice Updated"},
            {"id": 2, "name": "Bob Updated"},
        ])
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["meta"]["succeeded"] == 2
        assert data["meta"]["failed"] == 0
        assert data["data"][0]["name"] == "Alice Updated"
        assert data["data"][1]["name"] == "Bob Updated"

    def test_bulk_update_missing_id(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        resp = client.put("/api/users/bulk", json=[
            {"name": "No ID"},
        ])
        assert resp.status_code == 200
        assert resp.get_json()["meta"]["failed"] == 1

    def test_bulk_update_not_array(self, client):
        resp = client.put("/api/users/bulk", json={"id": 1, "name": "X"})
        assert resp.status_code == 400

    # --- Bulk delete ---

    def test_bulk_delete(self, client):
        client.post("/api/users", json={"name": "Alice", "email": "a@t.com", "age": 30})
        client.post("/api/users", json={"name": "Bob", "email": "b@t.com", "age": 25})
        resp = client.delete("/api/users/bulk", json=[1, 2])
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["meta"]["succeeded"] == 2
        assert data["meta"]["failed"] == 0
        # Verify they're gone
        resp = client.get("/api/users")
        assert resp.get_json()["meta"]["totalElements"] == 0

    def test_bulk_delete_not_found(self, client):
        resp = client.delete("/api/users/bulk", json=[999])
        assert resp.status_code == 200
        assert resp.get_json()["meta"]["failed"] == 1

    def test_bulk_delete_not_array(self, client):
        resp = client.delete("/api/users/bulk", json={"id": 1})
        assert resp.status_code == 400
