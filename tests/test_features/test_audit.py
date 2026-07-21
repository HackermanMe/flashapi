import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Note(BaseModel):
    title: str
    content: str = ""


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Note], database=db_path, audit=True)
    return TestClient(flash.app)


class TestAuditTrail:
    def test_create_records_audit(self, client):
        client.post("/api/notes", json={"title": "Hello", "content": "World"})
        resp = client.get("/api/notes/1/history")
        assert resp.status_code == 200
        history = resp.json()["data"]
        assert len(history) == 1
        assert history[0]["action"] == "CREATE"
        assert history[0]["entityId"] == "1"

    def test_update_records_diff(self, client):
        client.post("/api/notes", json={"title": "Original", "content": "Body"})
        client.put("/api/notes/1", json={"title": "Updated"})
        resp = client.get("/api/notes/1/history")
        history = resp.json()["data"]
        assert len(history) == 2
        update_entry = history[1]
        assert update_entry["action"] == "UPDATE"
        assert update_entry["changes"]["title"]["from"] == "Original"
        assert update_entry["changes"]["title"]["to"] == "Updated"

    def test_delete_records_audit(self, client):
        client.post("/api/notes", json={"title": "ToDelete"})
        client.delete("/api/notes/1")
        resp = client.get("/api/notes/1/history")
        history = resp.json()["data"]
        assert len(history) == 2
        assert history[1]["action"] == "DELETE"

    def test_history_empty_for_unknown(self, client):
        resp = client.get("/api/notes/999/history")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
