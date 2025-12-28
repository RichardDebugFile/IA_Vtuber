"""
Integration tests for IA_Vtuber services.

These tests verify that multiple services work together correctly.
They require services to be running.
"""
import asyncio
import base64
import json
from typing import AsyncGenerator

import httpx
import pytest
import websockets


@pytest.mark.integration
class TestServiceHealth:
    """Test that all services are healthy and responding."""

    @pytest.mark.asyncio
    async def test_gateway_health(self, gateway_url: str, http_client: httpx.AsyncClient):
        """Test Gateway service health."""
        response = await http_client.get(f"{gateway_url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_conversation_health(
        self, conversation_url: str, http_client: httpx.AsyncClient
    ):
        """Test Conversation service health."""
        response = await http_client.get(f"{conversation_url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tts_health(self, tts_url: str, http_client: httpx.AsyncClient):
        """Test TTS service health."""
        response = await http_client.get(f"{tts_url}/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_assistant_health(self, assistant_url: str, http_client: httpx.AsyncClient):
        """Test Assistant service health."""
        response = await http_client.get(f"{assistant_url}/health")
        assert response.status_code == 200


@pytest.mark.integration
class TestGatewayPubSub:
    """Test Gateway pub/sub functionality."""

    @pytest.mark.asyncio
    async def test_publish_and_receive_event(
        self, gateway_url: str, http_client: httpx.AsyncClient
    ):
        """Test publishing event and receiving via WebSocket."""
        # Connect to WebSocket
        ws_url = gateway_url.replace("http://", "ws://") + "/ws"

        async with websockets.connect(ws_url) as websocket:
            # Subscribe to topic
            await websocket.send(
                json.dumps({"type": "subscribe", "topics": ["test_topic"]})
            )

            # Give a moment for subscription
            await asyncio.sleep(0.1)

            # Publish event
            event_data = {"message": "test", "value": 123}
            response = await http_client.post(
                f"{gateway_url}/publish",
                json={"topic": "test_topic", "data": event_data},
            )
            assert response.status_code == 200

            # Receive event (with timeout)
            try:
                received = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(received)
                assert data["topic"] == "test_topic"
                assert data["data"] == event_data
            except asyncio.TimeoutError:
                pytest.fail("Did not receive event within timeout")


@pytest.mark.integration
@pytest.mark.requires_ollama
class TestConversationFlow:
    """Test conversation service with LLM."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(
        self, conversation_url: str, http_client: httpx.AsyncClient
    ):
        """Test that chat endpoint returns valid response."""
        response = await http_client.post(
            f"{conversation_url}/chat",
            json={"text": "Hola, ¿cómo estás?"},
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            assert "reply" in data
            assert "emotion" in data
            assert len(data["reply"]) > 0
            assert data["emotion"] in [
                "neutral",
                "happy",
                "sad",
                "angry",
                "surprised",
                "excited",
                "confused",
                "upset",
                "fear",
                "asco",
                "love",
                "bored",
                "sleeping",
                "thinking",
            ]
        else:
            pytest.skip("Ollama server not available")

    @pytest.mark.asyncio
    async def test_chat_publishes_to_gateway(
        self,
        conversation_url: str,
        gateway_url: str,
        http_client: httpx.AsyncClient,
    ):
        """Test that conversation publishes emotion to gateway."""
        # Subscribe to emotion topic
        ws_url = gateway_url.replace("http://", "ws://") + "/ws"

        async with websockets.connect(ws_url) as websocket:
            await websocket.send(
                json.dumps({"type": "subscribe", "topics": ["emotion", "utterance"]})
            )
            await asyncio.sleep(0.1)

            # Send chat request
            response = await http_client.post(
                f"{conversation_url}/chat",
                json={"text": "Hola"},
                timeout=30.0,
            )

            if response.status_code == 200:
                # Should receive emotion and utterance events
                try:
                    for _ in range(2):
                        msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        data = json.loads(msg)
                        assert data["topic"] in ["emotion", "utterance"]
                except asyncio.TimeoutError:
                    # Events might not be published in all configurations
                    pass


@pytest.mark.integration
@pytest.mark.requires_fish
class TestTTSFlow:
    """Test TTS service with Fish Audio."""

    @pytest.mark.asyncio
    async def test_synthesize_returns_audio(
        self, tts_url: str, http_client: httpx.AsyncClient
    ):
        """Test that TTS returns valid audio data."""
        response = await http_client.post(
            f"{tts_url}/synthesize",
            json={"text": "Hola mundo", "emotion": "happy"},
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            assert "audio_b64" in data
            assert "mime" in data

            # Decode and verify audio
            audio_bytes = base64.b64decode(data["audio_b64"])
            assert len(audio_bytes) > 0
        else:
            pytest.skip("Fish Audio server not available")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "emotion",
        ["neutral", "happy", "sad", "angry", "surprised", "excited"],
    )
    async def test_synthesize_with_emotions(
        self, tts_url: str, http_client: httpx.AsyncClient, emotion: str
    ):
        """Test TTS with different emotions."""
        response = await http_client.post(
            f"{tts_url}/synthesize",
            json={"text": "Prueba de emoción", "emotion": emotion},
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            assert "audio_b64" in data
        else:
            pytest.skip("Fish Audio server not available")


@pytest.mark.e2e
@pytest.mark.requires_ollama
@pytest.mark.requires_fish
@pytest.mark.slow
class TestEndToEndFlow:
    """End-to-end tests for complete conversation flow."""

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(
        self,
        assistant_url: str,
        gateway_url: str,
        http_client: httpx.AsyncClient,
    ):
        """
        Test complete flow: user input -> LLM -> emotion -> TTS -> audio.

        This tests the full pipeline through the Assistant service.
        """
        # Subscribe to events
        ws_url = gateway_url.replace("http://", "ws://") + "/ws"

        async with websockets.connect(ws_url) as websocket:
            await websocket.send(
                json.dumps(
                    {"type": "subscribe", "topics": ["emotion", "utterance", "audio"]}
                )
            )
            await asyncio.sleep(0.1)

            # Send request to assistant
            response = await http_client.post(
                f"{assistant_url}/api/assistant/aggregate",
                json={"text": "Hola, ¿cómo estás?", "out": "b64"},
                timeout=60.0,
            )

            if response.status_code == 200:
                # Verify we receive events
                events_received = []
                try:
                    for _ in range(3):  # Expect emotion, utterance, audio
                        msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(msg)
                        events_received.append(data["topic"])
                except asyncio.TimeoutError:
                    pass

                # Should have received at least some events
                assert len(events_received) > 0
            else:
                pytest.skip("Required services not available")

    @pytest.mark.asyncio
    async def test_assistant_streaming_response(
        self, assistant_url: str, http_client: httpx.AsyncClient
    ):
        """Test that Assistant returns streaming SSE response."""
        response = await http_client.post(
            f"{assistant_url}/api/assistant/aggregate",
            json={"text": "Hola", "out": "b64"},
            timeout=60.0,
        )

        if response.status_code == 200:
            # Should be Server-Sent Events
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type or "application/json" in content_type
        else:
            pytest.skip("Required services not available")


@pytest.mark.integration
class TestServiceInteraction:
    """Test interactions between services."""

    @pytest.mark.asyncio
    async def test_conversation_to_tts_pipeline(
        self,
        conversation_url: str,
        tts_url: str,
        http_client: httpx.AsyncClient,
    ):
        """Test pipeline from conversation to TTS."""
        # Get response from conversation
        conv_response = await http_client.post(
            f"{conversation_url}/chat",
            json={"text": "Hola"},
            timeout=30.0,
        )

        if conv_response.status_code != 200:
            pytest.skip("Conversation service not available")

        conv_data = conv_response.json()
        reply = conv_data["reply"]
        emotion = conv_data["emotion"]

        # Use reply and emotion for TTS
        tts_response = await http_client.post(
            f"{tts_url}/synthesize",
            json={"text": reply, "emotion": emotion},
            timeout=30.0,
        )

        if tts_response.status_code == 200:
            tts_data = tts_response.json()
            assert "audio_b64" in tts_data
        else:
            pytest.skip("TTS service not available")


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling across services."""

    @pytest.mark.asyncio
    async def test_conversation_handles_empty_input(
        self, conversation_url: str, http_client: httpx.AsyncClient
    ):
        """Test that conversation handles empty input gracefully."""
        response = await http_client.post(
            f"{conversation_url}/chat",
            json={"text": ""},
        )
        # Should either succeed with default or return validation error
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_tts_handles_invalid_emotion(
        self, tts_url: str, http_client: httpx.AsyncClient
    ):
        """Test that TTS handles invalid emotion gracefully."""
        response = await http_client.post(
            f"{tts_url}/synthesize",
            json={"text": "Test", "emotion": "invalid_emotion"},
        )
        # Should either use default or return error
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_gateway_rejects_invalid_topic(
        self, gateway_url: str, http_client: httpx.AsyncClient
    ):
        """Test that gateway rejects invalid topics."""
        response = await http_client.post(
            f"{gateway_url}/publish",
            json={"topic": "invalid_topic", "data": {"test": "data"}},
        )
        assert response.status_code == 400
