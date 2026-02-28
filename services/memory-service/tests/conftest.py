"""
Configuración compartida para los tests de integración del memory-service.

REQUISITO: El servicio debe estar corriendo antes de ejecutar los tests.
  1. start_db.bat   → PostgreSQL en localhost:8821
  2. start.bat      → API en http://127.0.0.1:8820
"""

import pytest
import httpx

BASE_URL = "http://127.0.0.1:8820"
TEST_USER = "__pytest__"      # marker para identificar datos de test en BD


@pytest.fixture(scope="session")
def client():
    """Cliente HTTP sincrónico apuntando a la API del memory-service."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def require_service_running(client):
    """Aborta la suite si el servicio no está levantado."""
    try:
        r = client.get("/health")
        if r.status_code != 200 or r.json().get("database") != "connected":
            pytest.exit(
                f"El memory-service responde pero la DB no está conectada: {r.text}",
                returncode=1,
            )
    except httpx.ConnectError:
        pytest.exit(
            "No se puede conectar al memory-service en http://127.0.0.1:8820.\n"
            "Ejecuta primero:  start_db.bat  y luego  start.bat",
            returncode=1,
        )


@pytest.fixture
def session_id(client):
    """
    Crea una sesión de test (opt_out_training=True) y la cierra al finalizar.
    Usar como fixture en tests que necesitan una sesión limpia.
    """
    r = client.post("/sessions", json={"user_id": TEST_USER, "opt_out_training": True})
    assert r.status_code == 201, f"No se pudo crear sesión: {r.text}"
    sid = r.json()["session_id"]
    yield sid
    client.post(f"/sessions/{sid}/end")


@pytest.fixture
def interaction_id(client, session_id):
    """
    Crea una interacción de test dentro de una sesión.
    Depende del fixture `session_id`.
    """
    r = client.post("/interactions", json={
        "session_id": session_id,
        "user_id": TEST_USER,
        "input_text": "Test input",
        "output_text": "Test output de Casiopy",
        "input_emotion": "neutral",
        "output_emotion": "flat",
        "conversation_turn": 1,
        "latency_ms": 500,
        "model_version": "gemma3-test",
    })
    assert r.status_code == 201, f"No se pudo crear interacción: {r.text}"
    return r.json()["interaction_id"]
