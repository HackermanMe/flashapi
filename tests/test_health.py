"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flashapi.adapters.fastapi import FlashAPI


class TestItem(BaseModel):
    name: str


@pytest.fixture
def app(tmp_path):
    """Create a test FastAPI app."""
    db_path = str(tmp_path / "test.db")
    flash = FlashAPI([TestItem], database=db_path)
    return flash.app


def test_liveness_probe(app):
    """Test GET /health returns liveness status."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime" in data
    assert isinstance(data["uptime"], int)


def test_readiness_probe(app):
    """Test GET /ready returns readiness status."""
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "uptime" in data
    assert "checks_passed" in data
    assert data["checks_passed"] >= 0  # At least 0 checks (in-memory DB has no check)
