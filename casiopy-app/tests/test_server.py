"""Tests de casiopy-app/server.py — todos offline (sin servicios externos).

Cubre:
- GET /health
- GET /config
- GET /  (SPA)
- GET /{path}  (SPA fallback)
- GET /static/js/app.js  (archivos estáticos)
- Variables de entorno reflejadas en /config
"""
import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Añadir raíz del proyecto (casiopy-app/) al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server as server_module
from server import app


@pytest.fixture
def client():
    """TestClient de FastAPI para casiopy-app."""
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_health_returns_200(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200


@pytest.mark.unit
def test_health_body_ok(client: TestClient):
    data = client.get("/health").json()
    assert data["status"]  == "ok"
    assert data["service"] == "casiopy-app"
    assert "version" in data


# ─────────────────────────────────────────────────────────────────────────────
# GET /config
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_config_returns_200(client: TestClient):
    assert client.get("/config").status_code == 200


@pytest.mark.unit
def test_config_has_gateway_keys(client: TestClient):
    data = client.get("/config").json()
    assert "gateway_url"    in data
    assert "gateway_ws"     in data
    assert "monitoring_url" in data


@pytest.mark.unit
def test_config_defaults_point_to_8800(client: TestClient):
    data = client.get("/config").json()
    assert "8800" in data["gateway_url"]
    assert "8800" in data["gateway_ws"]


@pytest.mark.unit
def test_config_gateway_url_is_http(client: TestClient):
    data = client.get("/config").json()
    assert data["gateway_url"].startswith("http")


@pytest.mark.unit
def test_config_gateway_ws_is_ws(client: TestClient):
    data = client.get("/config").json()
    assert data["gateway_ws"].startswith("ws")


@pytest.mark.unit
def test_config_reflects_env_override(monkeypatch):
    """Las variables de entorno deben propagarse a /config."""
    monkeypatch.setenv("GATEWAY_URL",    "http://custom-host:9999")
    monkeypatch.setenv("GATEWAY_WS",     "ws://custom-host:9999")
    monkeypatch.setenv("MONITORING_URL", "http://custom-host:9900")
    importlib.reload(server_module)
    c = TestClient(server_module.app)
    data = c.get("/config").json()
    assert data["gateway_url"]    == "http://custom-host:9999"
    assert data["gateway_ws"]     == "ws://custom-host:9999"
    assert data["monitoring_url"] == "http://custom-host:9900"
    # Restaurar defaults para no afectar otros tests
    monkeypatch.delenv("GATEWAY_URL",    raising=False)
    monkeypatch.delenv("GATEWAY_WS",     raising=False)
    monkeypatch.delenv("MONITORING_URL", raising=False)
    importlib.reload(server_module)


# ─────────────────────────────────────────────────────────────────────────────
# SPA — GET / y /{path}
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_root_returns_200(client: TestClient):
    assert client.get("/").status_code == 200


@pytest.mark.unit
def test_root_returns_html(client: TestClient):
    r = client.get("/")
    assert "text/html" in r.headers["content-type"]


@pytest.mark.unit
def test_root_html_contains_casiopy(client: TestClient):
    assert "Casiopy" in client.get("/").text


@pytest.mark.unit
def test_root_html_contains_app_js_reference(client: TestClient):
    assert "app.js" in client.get("/").text


@pytest.mark.unit
def test_spa_fallback_arbitrary_path(client: TestClient):
    r = client.get("/some/deep/nested/route")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.unit
def test_spa_fallback_returns_same_html_as_root(client: TestClient):
    root = client.get("/").text
    deep = client.get("/chat/session/42").text
    assert root == deep


# ─────────────────────────────────────────────────────────────────────────────
# Archivos estáticos
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_static_js_accessible(client: TestClient):
    r = client.get("/static/js/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


@pytest.mark.unit
def test_static_js_contains_init_function(client: TestClient):
    """app.js debe definir la función init() de arranque."""
    r = client.get("/static/js/app.js")
    assert "function init()" in r.text


@pytest.mark.unit
def test_static_js_contains_sendmessage(client: TestClient):
    r = client.get("/static/js/app.js")
    assert "sendMessage" in r.text


@pytest.mark.unit
def test_static_js_contains_orchestrate_chat(client: TestClient):
    """app.js debe llamar a /orchestrate/chat del gateway."""
    r = client.get("/static/js/app.js")
    assert "orchestrate/chat" in r.text


@pytest.mark.unit
def test_static_js_contains_stt(client: TestClient):
    r = client.get("/static/js/app.js")
    assert "orchestrate/stt" in r.text
