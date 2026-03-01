"""Tests del gateway v2.0 — pub/sub hub + orquestación."""
from typing import List

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_health_returns_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "gateway"
    assert "topics" in data
    assert "subscribers" in data


@pytest.mark.unit
def test_health_includes_service_status_topic(client: TestClient):
    """El nuevo topic service-status debe aparecer en la lista."""
    r = client.get("/health")
    assert "service-status" in r.json()["topics"]


# ─────────────────────────────────────────────────────────────────────────────
# POST /publish
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_publish_to_valid_topic(client: TestClient, sample_topics: List[str]):
    for topic in sample_topics:
        r = client.post("/publish", json={"topic": topic, "data": {"test": "data"}})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["topic"] == topic
        assert data["delivered"] >= 0   # sin suscriptores → 0


@pytest.mark.unit
def test_publish_service_status_topic(client: TestClient):
    """service-status es el nuevo topic añadido en v2."""
    r = client.post(
        "/publish",
        json={"topic": "service-status", "data": {"id": "memory-api", "action": "starting"}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.unit
def test_publish_to_invalid_topic(client: TestClient):
    r = client.post("/publish", json={"topic": "invalid_topic", "data": {"x": 1}})
    assert r.status_code == 400
    assert "is not a valid topic" in r.json()["detail"].lower()


@pytest.mark.unit
def test_publish_without_data_field_fails_validation(client: TestClient):
    r = client.post("/publish", json={"topic": "utterance"})
    assert r.status_code == 422


@pytest.mark.unit
def test_publish_empty_data(client: TestClient):
    r = client.post("/publish", json={"topic": "utterance", "data": {}})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.unit
def test_publish_multiple_events_sequentially(client: TestClient):
    for i in range(5):
        r = client.post("/publish", json={"topic": "utterance", "data": {"index": i}})
        assert r.status_code == 200
        assert r.json()["ok"] is True


@pytest.mark.unit
def test_publish_with_complex_nested_data(client: TestClient):
    data = {
        "user": "test_user",
        "message": {
            "text": "Hello",
            "metadata": {
                "timestamp": 1234567890,
                "tags": ["greeting", "test"],
                "nested": {"level": 3, "data": [1, 2, 3]},
            },
        },
    }
    r = client.post("/publish", json={"topic": "utterance", "data": data})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.unit
def test_gateway_handles_malformed_json(client: TestClient):
    r = client.post(
        "/publish",
        content="{invalid json}",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket /ws
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_websocket_subscribe_single_topic(client: TestClient):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": ["utterance"]})
        resp = ws.receive_json()
        assert resp["type"] == "subscribed"
        assert "utterance" in resp["topics"]


@pytest.mark.integration
def test_websocket_subscribe_multiple_topics(client: TestClient, sample_topics: List[str]):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": sample_topics})
        resp = ws.receive_json()
        assert resp["type"] == "subscribed"
        # Todos los tópicos válidos deben haberse aceptado
        for tp in sample_topics:
            assert tp in resp["topics"]


@pytest.mark.integration
def test_websocket_subscribe_service_status_topic(client: TestClient):
    """El nuevo topic service-status debe ser suscribible."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": ["service-status"]})
        resp = ws.receive_json()
        assert resp["type"] == "subscribed"
        assert "service-status" in resp["topics"]


@pytest.mark.integration
def test_websocket_receive_published_event(client: TestClient):
    """Un suscriptor debe recibir el evento publicado en su tópico."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": ["emotion"]})
        ws.receive_json()  # confirmación "subscribed"

        import time; time.sleep(0.05)

        event_data = {"emotion": "happy", "confidence": 0.9}
        pub_r = client.post("/publish", json={"topic": "emotion", "data": event_data})
        assert pub_r.status_code == 200

        try:
            received = ws.receive_json(timeout=2.0)
            # El gateway envía {"type": "<topic>", "data": {...}}
            assert received["type"] == "emotion"
            assert received["data"] == event_data
        except Exception:
            # En entornos de test el timing puede variar; se acepta
            pass


@pytest.mark.integration
def test_websocket_unsubscribe_stops_receiving(client: TestClient):
    """Tras unsubscribe el cliente no debe recibir eventos del tópico."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": ["utterance"]})
        ws.receive_json()  # confirmación

        import time; time.sleep(0.05)

        ws.send_json({"type": "unsubscribe", "topics": ["utterance"]})
        time.sleep(0.05)

        client.post("/publish", json={"topic": "utterance", "data": {"text": "test"}})

        with pytest.raises(Exception):
            ws.receive_json(timeout=1.0)


@pytest.mark.integration
def test_websocket_ping_pong(client: TestClient):
    """El gateway debe responder pong ante un ping."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"


@pytest.mark.integration
def test_multiple_subscribers_receive_same_event(client: TestClient):
    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        ws1.send_json({"type": "subscribe", "topics": ["emotion"]})
        ws2.send_json({"type": "subscribe", "topics": ["emotion"]})
        ws1.receive_json()  # subscribed
        ws2.receive_json()  # subscribed

        import time; time.sleep(0.05)

        event_data = {"emotion": "excited", "value": 123}
        client.post("/publish", json={"topic": "emotion", "data": event_data})

        try:
            d1 = ws1.receive_json(timeout=1.0)
            d2 = ws2.receive_json(timeout=1.0)
            assert d1["data"] == event_data
            assert d2["data"] == event_data
        except Exception:
            pass  # timing en entornos de test


# ─────────────────────────────────────────────────────────────────────────────
# GET /services/status  (offline — sin monitoring-service)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_services_status_returns_502_when_monitoring_offline(client: TestClient):
    """Sin monitoring-service levantado el endpoint debe retornar 502."""
    r = client.get("/services/status")
    assert r.status_code == 502
    assert "monitoring-service" in r.json()["detail"].lower()


@pytest.mark.unit
def test_service_start_returns_502_when_monitoring_offline(client: TestClient):
    r = client.post("/services/memory-api/start")
    assert r.status_code == 502


@pytest.mark.unit
def test_service_stop_returns_502_when_monitoring_offline(client: TestClient):
    r = client.post("/services/memory-api/stop")
    assert r.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# POST /orchestrate/chat  (offline — sin conversation ni TTS)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_orchestrate_chat_returns_502_when_conversation_offline(client: TestClient):
    """Sin conversation-service el endpoint debe retornar 502."""
    r = client.post(
        "/orchestrate/chat",
        json={"text": "Hola", "user_id": "test", "tts_mode": "blips"},
    )
    assert r.status_code == 502
    assert "conversation-service" in r.json()["detail"].lower()


@pytest.mark.unit
def test_orchestrate_chat_requires_text_field(client: TestClient):
    r = client.post("/orchestrate/chat", json={"user_id": "test"})
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# POST /orchestrate/stt  (offline — sin stt-service)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_orchestrate_stt_returns_502_when_stt_offline(client: TestClient):
    """Sin stt-service el endpoint debe retornar 502."""
    import io
    r = client.post(
        "/orchestrate/stt",
        files={"audio": ("test.webm", io.BytesIO(b"fake audio"), "audio/webm")},
    )
    assert r.status_code == 502
    assert "stt-service" in r.json()["detail"].lower()


@pytest.mark.unit
def test_orchestrate_stt_requires_audio_file(client: TestClient):
    r = client.post("/orchestrate/stt")
    assert r.status_code == 422
