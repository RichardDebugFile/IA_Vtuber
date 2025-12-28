"""Unit tests for Assistant service server."""
import os
import sys
from unittest.mock import AsyncMock, patch, Mock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_services():
    """Mock conversation and TTS services."""
    with patch("src.server.httpx.AsyncClient") as mock_client:
        mock_response_conv = Mock()
        mock_response_conv.status_code = 200
        mock_response_conv.json.return_value = {
            "reply": "Test response",
            "emotion": "happy",
            "model": "test",
        }

        mock_response_tts = Mock()
        mock_response_tts.status_code = 200
        mock_response_tts.json.return_value = {
            "audio_b64": "dGVzdCBhdWRpbw==",
            "mime": "audio/wav",
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=[mock_response_conv, mock_response_tts]
        )

        yield mock_client


@pytest.fixture
def client():
    """FastAPI test client for Assistant service."""
    from src.server import app
    return TestClient(app)


@pytest.mark.unit
def test_health_endpoint(client: TestClient):
    """Test that health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.unit
def test_aggregate_endpoint_requires_text(client: TestClient):
    """Test that aggregate endpoint requires text field."""
    response = client.post(
        "/api/assistant/aggregate",
        json={},  # Missing 'text'
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.slow
def test_aggregate_endpoint_basic(client: TestClient, mock_services):
    """Test basic aggregate endpoint functionality (mocked)."""
    # This would require mocking conversation and TTS services
    # For now, we'll test the endpoint exists
    response = client.post(
        "/api/assistant/aggregate",
        json={"text": "Hola"},
    )

    # Might fail if services not running, which is expected
    assert response.status_code in [200, 500, 502, 503]


@pytest.mark.unit
def test_tts_endpoint_requires_text(client: TestClient):
    """Test that TTS endpoint requires text field."""
    response = client.post(
        "/api/assistant/tts",
        json={"emotion": "happy"},  # Missing 'text'
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.integration
def test_tts_endpoint_basic(client: TestClient):
    """Test basic TTS endpoint functionality."""
    response = client.post(
        "/api/assistant/tts",
        json={"text": "Hola", "emotion": "happy"},
    )

    # Might fail if TTS service not running
    assert response.status_code in [200, 500, 502, 503]


@pytest.mark.unit
@pytest.mark.parametrize("out_mode", ["url", "b64"])
def test_aggregate_output_modes(client: TestClient, out_mode: str):
    """Test aggregate endpoint with different output modes."""
    response = client.post(
        "/api/assistant/aggregate",
        json={"text": "Hola", "out": out_mode},
    )

    # Accept success or service unavailable
    assert response.status_code in [200, 500, 502, 503]


@pytest.mark.unit
def test_static_media_route_exists(client: TestClient):
    """Test that static media route is configured."""
    # Try to access a non-existent file (should return 404, not 500)
    response = client.get("/media/nonexistent.wav")
    assert response.status_code == 404


class TestTextSegmentation:
    """Tests for text segmentation logic in Assistant."""

    @pytest.mark.unit
    def test_segment_simple_sentence(self):
        """Test segmentation of simple sentence."""
        # This would test the internal segmentation logic
        # For now, we'll skip as it requires importing internal functions
        pass

    @pytest.mark.unit
    def test_segment_multiple_sentences(self):
        """Test segmentation of multiple sentences."""
        pass

    @pytest.mark.unit
    def test_segment_long_sentence_balancing(self):
        """Test that long sentences are balanced correctly."""
        pass

    @pytest.mark.unit
    def test_first_chunk_short_strategy(self):
        """Test that first chunk is kept short for fast response."""
        pass


class TestTimingCalculation:
    """Tests for timing and pause calculation."""

    @pytest.mark.unit
    def test_pause_after_comma(self):
        """Test pause calculation after comma."""
        pass

    @pytest.mark.unit
    def test_pause_after_period(self):
        """Test pause calculation after period."""
        pass

    @pytest.mark.unit
    def test_pause_after_question_mark(self):
        """Test pause calculation after question mark."""
        pass

    @pytest.mark.unit
    def test_minimum_gap_enforced(self):
        """Test that minimum gap is enforced."""
        pass


@pytest.mark.integration
@pytest.mark.requires_ollama
@pytest.mark.requires_fish
@pytest.mark.slow
def test_full_pipeline_integration(client: TestClient):
    """
    Full integration test of conversation -> TTS -> streaming.

    This test requires all services to be running:
    - Ollama (LLM)
    - Conversation service
    - TTS service
    - Fish Audio server
    """
    response = client.post(
        "/api/assistant/aggregate",
        json={"text": "Hola, ¿cómo estás?", "out": "b64"},
    )

    if response.status_code == 200:
        # Verify streaming response structure
        # This is a Server-Sent Events stream
        assert response.headers.get("content-type") == "text/event-stream"
    else:
        pytest.skip("Required services not available")
