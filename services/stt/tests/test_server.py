"""Tests for STT server endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from src.server import app
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")

    # May fail if model not loaded, but endpoint should exist
    assert response.status_code in (200, 503)

    if response.status_code == 200:
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "stt-service"
        assert "model" in data
        assert "device" in data


def test_transcribe_endpoint_exists(client):
    """Test that transcribe endpoint exists."""
    # This will fail without a file, but verifies the endpoint exists
    response = client.post("/transcribe")

    # Should get 422 (validation error) not 404 (not found)
    assert response.status_code == 422
