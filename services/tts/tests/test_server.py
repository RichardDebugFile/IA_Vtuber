"""Unit tests for TTS service server."""
import base64
import os
import sys
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.server import app


@pytest.fixture
def client():
    """FastAPI test client for TTS service."""
    return TestClient(app)


@pytest.mark.unit
def test_health_endpoint(client: TestClient):
    """Test that health endpoint (liveness probe) returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert data["ok"] is True
    assert "status" in data
    assert data["status"] == "alive"


@pytest.mark.unit
def test_readiness_endpoint(client: TestClient):
    """Test that readiness endpoint checks backend health."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "status" in data
    # backend_alive can be None if no Fish Audio backend configured
    assert "backend_alive" in data or data.get("reason") == "fish_audio_unhealthy"


@pytest.mark.unit
def test_synthesize_endpoint_basic(client: TestClient):
    """Test basic synthesize endpoint functionality."""
    response = client.post(
        "/synthesize",
        json={"text": "Hola mundo", "emotion": "neutral", "backend": "local"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "audio_b64" in data
    assert "mime" in data

    # Decode and verify it's valid base64
    audio_bytes = base64.b64decode(data["audio_b64"])
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0


@pytest.mark.unit
def test_synthesize_requires_text(client: TestClient):
    """Test that synthesize endpoint requires text field."""
    response = client.post(
        "/synthesize",
        json={"emotion": "neutral"},  # Missing 'text'
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_synthesize_default_emotion(client: TestClient):
    """Test that synthesize uses default emotion if not provided."""
    response = client.post(
        "/synthesize",
        json={"text": "Hola", "backend": "local"},  # No emotion specified
    )

    # Should succeed with default emotion
    assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("emotion", [
    "neutral", "happy", "sad", "angry", "surprised",
    "excited", "confused", "upset", "fear", "asco",
    "love", "bored", "sleeping", "thinking"
])
def test_synthesize_all_emotions(client: TestClient, emotion: str):
    """Test synthesize endpoint with all valid emotions."""
    response = client.post(
        "/synthesize",
        json={"text": "Prueba", "emotion": emotion, "backend": "local"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "audio_b64" in data


@pytest.mark.unit
def test_synthesize_with_empty_text(client: TestClient):
    """Test synthesize with empty text should fail validation."""
    response = client.post(
        "/synthesize",
        json={"text": "", "emotion": "neutral", "backend": "local"},
    )

    # Should fail validation (min_length=1)
    assert response.status_code == 422


@pytest.mark.unit
def test_synthesize_with_long_text(client: TestClient):
    """Test synthesize with long text (within limit)."""
    long_text = "Esta es una prueba. " * 100  # ~2000 chars, within 5000 limit
    response = client.post(
        "/synthesize",
        json={"text": long_text, "emotion": "neutral", "backend": "local"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "audio_b64" in data


@pytest.mark.unit
def test_synthesize_with_too_long_text(client: TestClient):
    """Test synthesize with text exceeding max length."""
    too_long_text = "A" * 5001  # Exceeds 5000 char limit
    response = client.post(
        "/synthesize",
        json={"text": too_long_text, "emotion": "neutral", "backend": "local"},
    )

    # Should fail validation (max_length=5000)
    assert response.status_code == 422


@pytest.mark.unit
def test_synthesize_with_special_characters(client: TestClient):
    """Test synthesize with special characters and accents."""
    special_text = "¡Hola! ¿Cómo estás? ñ á é í ó ú"
    response = client.post(
        "/synthesize",
        json={"text": special_text, "emotion": "neutral", "backend": "local"},
    )

    assert response.status_code == 200


@pytest.mark.unit
def test_synthesize_backend_parameter(client: TestClient):
    """Test synthesize with valid backend parameter."""
    response = client.post(
        "/synthesize",
        json={"text": "Hola", "emotion": "neutral", "backend": "local"},
    )

    # Should accept local backend for testing
    assert response.status_code == 200


@pytest.mark.unit
def test_synthesize_invalid_backend(client: TestClient):
    """Test synthesize with invalid backend parameter."""
    response = client.post(
        "/synthesize",
        json={"text": "Hola", "emotion": "neutral", "backend": "invalid"},
    )

    # Should fail with 400 Bad Request
    assert response.status_code == 400


@pytest.mark.unit
def test_synthesize_invalid_emotion(client: TestClient):
    """Test synthesize with invalid emotion (should use neutral as fallback)."""
    response = client.post(
        "/synthesize",
        json={"text": "Hola", "emotion": "invalid_emotion", "backend": "local"},
    )

    # Should succeed with fallback to neutral
    assert response.status_code == 200


@pytest.mark.unit
def test_synthesize_returns_valid_base64(client: TestClient):
    """Test that synthesize returns valid base64 encoded audio."""
    response = client.post(
        "/synthesize",
        json={"text": "Prueba de audio", "emotion": "happy", "backend": "local"},
    )

    assert response.status_code == 200
    data = response.json()

    # Should be able to decode without error
    try:
        audio_bytes = base64.b64decode(data["audio_b64"])
        assert isinstance(audio_bytes, bytes)
    except Exception as e:
        pytest.fail(f"Failed to decode base64: {e}")


@pytest.mark.unit
def test_synthesize_mime_type(client: TestClient):
    """Test that synthesize returns correct MIME type."""
    response = client.post(
        "/synthesize",
        json={"text": "Prueba", "emotion": "neutral", "backend": "local"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "mime" in data
    # Local backend returns octet-stream (not real WAV)
    assert data["mime"] in ["audio/wav", "application/octet-stream"]


@pytest.mark.integration
@pytest.mark.requires_fish
def test_synthesize_with_real_fish_backend():
    """Test synthesize with real Fish Audio backend (integration test)."""
    # This test requires Fish Audio server to be running
    client = TestClient(app)

    response = client.post(
        "/synthesize",
        json={"text": "Hola mundo", "emotion": "happy", "backend": "http"},
    )

    if response.status_code == 200:
        data = response.json()
        assert "audio_b64" in data
        audio_bytes = base64.b64decode(data["audio_b64"])
        # Real audio should be larger than mock
        assert len(audio_bytes) > 100
    else:
        pytest.skip("Fish Audio server not available")
