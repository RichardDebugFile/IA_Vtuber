"""Pytest fixtures for Assistant service tests."""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_conversation_response():
    """Sample response from conversation service."""
    return {
        "reply": "Hola, ¿cómo estás?",
        "emotion": "happy",
        "model": "gemma3",
    }


@pytest.fixture
def sample_tts_response():
    """Sample response from TTS service."""
    return {
        "audio_b64": "dGVzdCBhdWRpbyBkYXRh",  # "test audio data" in base64
        "mime": "audio/wav",
    }


@pytest.fixture
def mock_http_client():
    """Mock httpx client for testing."""
    mock = AsyncMock()
    return mock
