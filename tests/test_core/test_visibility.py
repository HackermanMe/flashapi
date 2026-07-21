import pytest
from pydantic import BaseModel, Field

from flashapi.fastapi import FlashAPI


class UserWithVisibility(BaseModel):
    name: str
    email: str
    password: str = Field(json_schema_extra={"flash": {"writeonly": True}})
    internal_note: str = Field(default="", json_schema_extra={"flash": {"hidden": True}})
    created_at: str = Field(default="", json_schema_extra={"flash": {"readonly": True}})
    ssn: str = Field(default="", json_schema_extra={"flash": {"export_exclude": True}})


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[UserWithVisibility], database=db_path)
    return TestClient(flash.app)


class TestFieldVisibility:
    def test_writeonly_not_in_response(self, client):
        resp = client.post("/api/userwithvisibilities", json={
            "name": "Alice",
            "email": "a@b.com",
            "password": "secret123",
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "password" not in data
        assert data["name"] == "Alice"

    def test_writeonly_not_in_list(self, client):
        client.post("/api/userwithvisibilities", json={
            "name": "Alice",
            "email": "a@b.com",
            "password": "secret",
        })
        resp = client.get("/api/userwithvisibilities")
        for item in resp.json()["data"]:
            assert "password" not in item

    def test_hidden_not_in_response(self, client):
        resp = client.post("/api/userwithvisibilities", json={
            "name": "Alice",
            "email": "a@b.com",
            "password": "secret",
            "internal_note": "admin note",
        })
        data = resp.json()["data"]
        assert "internal_note" not in data

    def test_readonly_in_response(self, client):
        client.post("/api/userwithvisibilities", json={
            "name": "Alice",
            "email": "a@b.com",
            "password": "secret",
        })
        resp = client.get("/api/userwithvisibilities/1")
        data = resp.json()["data"]
        assert "created_at" in data

    def test_readonly_not_writable(self, client):
        resp = client.post("/api/userwithvisibilities", json={
            "name": "Alice",
            "email": "a@b.com",
            "password": "secret",
            "created_at": "2026-01-01",
        })
        data = resp.json()["data"]
        assert data.get("created_at") != "2026-01-01"
