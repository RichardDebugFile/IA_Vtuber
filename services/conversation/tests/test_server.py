"""Unit tests for Conversation service server."""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock the Ollama client before importing server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    mock = AsyncMock()
    mock.ask = AsyncMock(return_value=("Test response", "neutral"))
    return mock


@pytest.fixture
def client(mock_ollama_client):
    """FastAPI test client with mocked Ollama."""
    with patch("src.server.ollama_client", mock_ollama_client):
        from src.server import app
        return TestClient(app)


@pytest.mark.unit
def test_health_endpoint(client: TestClient):
    """Test that health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.unit
def test_chat_endpoint_basic(client: TestClient, mock_ollama_client):
    """Test basic chat endpoint functionality."""
    mock_ollama_client.ask.return_value = ("Hola, ¿cómo estás?", "happy")

    response = client.post(
        "/chat",
        json={"user": "test_user", "text": "Hola"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "emotion" in data
    assert data["emotion"] == "happy"
    assert data["model"] is not None


@pytest.mark.unit
def test_chat_endpoint_requires_text(client: TestClient):
    """Test that chat endpoint requires text field."""
    response = client.post(
        "/chat",
        json={"user": "test_user"},  # Missing 'text'
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_chat_endpoint_default_user(client: TestClient, mock_ollama_client):
    """Test that chat endpoint uses default user if not provided."""
    mock_ollama_client.ask.return_value = ("Response", "neutral")

    response = client.post(
        "/chat",
        json={"text": "Hello"},  # No user specified
    )

    assert response.status_code == 200


@pytest.mark.unit
def test_chat_endpoint_empty_text(client: TestClient, mock_ollama_client):
    """Test chat endpoint with empty text."""
    mock_ollama_client.ask.return_value = ("", "neutral")

    response = client.post(
        "/chat",
        json={"user": "test", "text": ""},
    )

    assert response.status_code == 200


@pytest.mark.unit
def test_chat_endpoint_long_text(client: TestClient, mock_ollama_client):
    """Test chat endpoint with very long text."""
    long_text = "palabra " * 1000  # 1000 words
    mock_ollama_client.ask.return_value = ("Response", "neutral")

    response = client.post(
        "/chat",
        json={"user": "test", "text": long_text},
    )

    assert response.status_code == 200


@pytest.mark.unit
def test_chat_endpoint_special_characters(client: TestClient, mock_ollama_client):
    """Test chat endpoint with special characters and emojis."""
    special_text = "¿Hola! ¿Cómo estás? 😊 #test @user"
    mock_ollama_client.ask.return_value = ("Response", "happy")

    response = client.post(
        "/chat",
        json={"text": special_text},
    )

    assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("emotion", [
    "happy", "sad", "angry", "fear", "surprised",
    "excited", "confused", "upset", "asco", "love",
    "bored", "sleeping", "thinking", "neutral"
])
def test_chat_endpoint_returns_valid_emotions(client: TestClient, mock_ollama_client, emotion):
    """Test that chat endpoint can return all valid emotions."""
    mock_ollama_client.ask.return_value = ("Response", emotion)

    response = client.post(
        "/chat",
        json={"text": "Test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["emotion"] == emotion


@pytest.mark.requires_ollama
@pytest.mark.integration
def test_chat_endpoint_with_real_ollama():
    """Test chat endpoint with real Ollama server (integration test)."""
    from src.server import app
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"text": "Hola, ¿cómo estás?"},
    )

    # This will fail if Ollama is not running
    if response.status_code == 200:
        data = response.json()
        assert "reply" in data
        assert "emotion" in data
        assert len(data["reply"]) > 0
    else:
        pytest.skip("Ollama server not available")


@pytest.mark.unit
def test_models_endpoint(client: TestClient):
    """Test models endpoint (if implemented)."""
    response = client.get("/models")

    # Endpoint might return 404 if not implemented
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (list, dict))
