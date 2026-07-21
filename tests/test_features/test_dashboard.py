import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI


class Task(BaseModel):
    title: str


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Task], database=db_path)
    return TestClient(flash.app)


class TestDashboard:
    def test_dashboard_html(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        assert "FlashAPI Dashboard" in resp.text

    def test_metrics_json(self, client):
        resp = client.get("/api/dashboard/metrics.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "generatedAt" in data
        assert "uptimeSeconds" in data
        assert "entities" in data
        assert "totals" in data
        assert "webhooks" in data
        assert "recentEvents" in data

    def test_metrics_entity_registered(self, client):
        resp = client.get("/api/dashboard/metrics.json")
        data = resp.json()
        assert "Task" in data["entities"]
        entity = data["entities"]["Task"]
        assert entity["softDelete"] is True
        assert "operations" in entity

    def test_metrics_records_operations(self, client):
        client.post("/api/tasks", json={"title": "Hello"})
        client.get("/api/tasks")

        resp = client.get("/api/dashboard/metrics.json")
        data = resp.json()
        assert data["totals"]["creates"] >= 1
        assert data["totals"]["total"] >= 2
        assert len(data["recentEvents"]) >= 2
