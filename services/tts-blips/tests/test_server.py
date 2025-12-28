"""Tests for FastAPI server."""
import base64

import pytest
from fastapi.testclient import TestClient

from src.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["sample_rate"] == 44100


def test_generate_blips_basic(client):
    """Test basic blips generation."""
    response = client.post("/blips/generate", json={
        "text": "Hola",
        "emotion": "neutral",
        "speed": 20.0,
        "volume": 0.7,
    })

    assert response.status_code == 200

    data = response.json()
    assert "audio_b64" in data
    assert data["num_blips"] > 0
    assert data["duration_ms"] > 0
    assert data["emotion"] == "neutral"
    assert data["text_length"] == 4

    # Verify base64 audio decodes properly
    audio_bytes = base64.b64decode(data["audio_b64"])
    assert len(audio_bytes) > 0
    assert audio_bytes[:4] == b"RIFF"  # WAV header


def test_generate_blips_with_emotion(client):
    """Test blips generation with different emotions."""
    emotions = ["happy", "sad", "excited", "angry"]

    for emotion in emotions:
        response = client.post("/blips/generate", json={
            "text": "Test",
            "emotion": emotion,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["emotion"] == emotion


def test_generate_blips_validation(client):
    """Test request validation."""
    # Empty text
    response = client.post("/blips/generate", json={
        "text": "",
    })
    assert response.status_code == 422  # Validation error

    # Speed out of range
    response = client.post("/blips/generate", json={
        "text": "Test",
        "speed": 100.0,  # Max is 40.0
    })
    assert response.status_code == 422

    # Volume out of range
    response = client.post("/blips/generate", json={
        "text": "Test",
        "volume": 2.0,  # Max is 1.0
    })
    assert response.status_code == 422


def test_preview_blip(client):
    """Test single blip preview."""
    response = client.get("/blips/preview", params={
        "char": "a",
        "emotion": "neutral",
    })

    assert response.status_code == 200

    data = response.json()
    assert "audio_b64" in data
    assert data["char"] == "a"
    assert data["emotion"] == "neutral"

    # Verify audio
    audio_bytes = base64.b64decode(data["audio_b64"])
    assert len(audio_bytes) > 0
    assert audio_bytes[:4] == b"RIFF"


def test_preview_different_chars(client):
    """Test preview with different characters."""
    chars = ["a", "s", "m"]

    audios = []
    for char in chars:
        response = client.get("/blips/preview", params={"char": char})
        assert response.status_code == 200
        audios.append(response.json()["audio_b64"])

    # Different characters should produce slightly different blips
    # (due to vowel vs consonant variations)
    assert len(set(audios)) > 1  # Not all the same
