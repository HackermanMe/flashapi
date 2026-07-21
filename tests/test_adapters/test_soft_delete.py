import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Task(BaseModel):
    title: str
    done: bool = False


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Task], database=db_path)
    return TestClient(flash.app)


class TestSoftDelete:
    def test_delete_is_soft(self, client):
        client.post("/api/tasks", json={"title": "Buy milk"})
        resp = client.delete("/api/tasks/1")
        assert resp.status_code == 204

        resp = client.get("/api/tasks/1")
        assert resp.status_code == 404

    def test_deleted_not_in_list(self, client):
        client.post("/api/tasks", json={"title": "Task 1"})
        client.post("/api/tasks", json={"title": "Task 2"})
        client.delete("/api/tasks/1")

        resp = client.get("/api/tasks")
        assert resp.json()["meta"]["totalElements"] == 1
        assert resp.json()["data"][0]["title"] == "Task 2"

    def test_deleted_visible_with_param(self, client):
        client.post("/api/tasks", json={"title": "Task 1"})
        client.delete("/api/tasks/1")

        resp = client.get("/api/tasks?deleted=true")
        assert resp.json()["meta"]["totalElements"] == 1
        assert resp.json()["data"][0]["title"] == "Task 1"

    def test_restore(self, client):
        client.post("/api/tasks", json={"title": "Task 1"})
        client.delete("/api/tasks/1")

        resp = client.post("/api/tasks/1/restore")
        assert resp.status_code == 204

        resp = client.get("/api/tasks/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Task 1"

    def test_restore_not_deleted_returns_404(self, client):
        client.post("/api/tasks", json={"title": "Task 1"})
        resp = client.post("/api/tasks/1/restore")
        assert resp.status_code == 404

    def test_restore_nonexistent_returns_404(self, client):
        resp = client.post("/api/tasks/999/restore")
        assert resp.status_code == 404


class TestBulkCreate:
    def test_bulk_create(self, client):
        resp = client.post("/api/tasks/bulk", json=[
            {"title": "Task 1"},
            {"title": "Task 2"},
            {"title": "Task 3"},
        ])
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["data"]) == 3
        assert data["meta"]["total"] == 3
        assert data["meta"]["succeeded"] == 3
        assert data["meta"]["failed"] == 0

    def test_bulk_create_empty(self, client):
        resp = client.post("/api/tasks/bulk", json=[])
        assert resp.status_code == 201
        assert resp.json()["meta"]["total"] == 0

    def test_bulk_create_invalid_body(self, client):
        resp = client.post("/api/tasks/bulk", json={"title": "not an array"})
        assert resp.status_code == 400
