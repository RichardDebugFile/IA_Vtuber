"""Pytest fixtures for Gateway service tests."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app


@pytest.fixture
def client():
    """FastAPI test client for Gateway service."""
    return TestClient(app)


@pytest.fixture
def sample_topics():
    """Lista de tópicos válidos del pub/sub (v2: añade service-status)."""
    return ["utterance", "emotion", "avatar-action", "audio", "service-status"]


@pytest.fixture
def sample_event_data():
    """Sample event data for publishing."""
    return {
        "utterance": {"text": "Hello world", "user": "test_user"},
        "emotion": {"emotion": "happy", "confidence": 0.95},
        "avatar-action": {"action": "wave", "duration": 2.0},
        "audio": {"url": "http://example.com/audio.wav", "duration_ms": 1500},
    }
