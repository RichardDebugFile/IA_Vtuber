"""
Tests de búsqueda semántica y personalidad — Fase 3 (integración).

Todos los tests en este archivo requieren el memory-service corriendo en 8820.
El conftest.py abortará la sesión si el servicio no está disponible.

Para tests offline (sin servicios) ver:
  tests/offline/test_embedding_offline.py

Ejecutar:
  cd services/memory-service
  python -m pytest tests/test_semantic.py -v
"""

import time

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# TestEmbedEndpoint — GET /embed
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedEndpoint:
    """Valida GET /embed."""

    def test_embed_returns_384_dimensions(self, client):
        r = client.get("/embed", params={"text": "Hola Casiopy"})
        assert r.status_code == 200
        data = r.json()
        assert data["dimensions"] == 384
        assert len(data["embedding"]) == 384

    def test_embed_empty_text_returns_zeros(self, client):
        r = client.get("/embed", params={"text": ""})
        assert r.status_code == 200
        data = r.json()
        assert all(v == 0.0 for v in data["embedding"])


# ─────────────────────────────────────────────────────────────────────────────
# TestSemanticSearch — GET /search
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticSearch:
    """Valida GET /search."""

    def test_search_returns_correct_structure(self, client):
        r = client.get("/search", params={"q": "videojuegos anime"})
        assert r.status_code == 200
        data = r.json()
        assert "query"     in data
        assert "results"   in data
        assert "count"     in data
        assert "threshold" in data

    def test_results_respect_threshold(self, client):
        threshold = 0.75
        r = client.get("/search", params={"q": "anime", "threshold": threshold})
        assert r.status_code == 200
        for result in r.json()["results"]:
            assert result["similarity"] >= threshold, (
                f"Resultado con similitud {result['similarity']} < threshold {threshold}"
            )

    def test_results_respect_limit(self, client):
        limit = 2
        r = client.get("/search", params={"q": "hola", "limit": limit})
        assert r.status_code == 200
        assert len(r.json()["results"]) <= limit

    def test_gibberish_query_returns_no_results_with_high_threshold(self, client):
        r = client.get(
            "/search",
            params={"q": "xkzwqmplrtnbvs", "threshold": 0.99, "limit": 10},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestInteractionWithEmbedding — requiere BD
# ─────────────────────────────────────────────────────────────────────────────

class TestInteractionWithEmbedding:
    """Verifica que /search no falla tras almacenar una interacción."""

    def test_search_does_not_fail_after_store(self, client):
        # Crear sesión
        s = client.post("/sessions", json={"user_id": "test_semantic"})
        assert s.status_code == 201
        session_id = s.json()["session_id"]

        # Almacenar interacción
        inter = client.post("/interactions", json={
            "session_id":   session_id,
            "input_text":   "¿Qué opinas de los videojuegos de rol japonés?",
            "output_text":  "¡Me encantan! Los JRPGs son mi género favorito.",
            "input_emotion":  "curious",
            "output_emotion": "excited",
        })
        assert inter.status_code == 201

        # Esperar a que el background task de embedding termine
        time.sleep(2)

        # La búsqueda no debe fallar aunque aún no haya embeddings indexados
        r = client.get("/search", params={"q": "videojuegos japoneses", "threshold": 0.5})
        assert r.status_code == 200
        assert isinstance(r.json()["results"], list)


# ─────────────────────────────────────────────────────────────────────────────
# TestPersonalityEndpoints — /personality/*
# ─────────────────────────────────────────────────────────────────────────────

class TestPersonalityEndpoints:
    """Valida los endpoints /personality/*."""

    def test_compute_returns_201_or_422(self, client):
        r = client.post("/personality/compute", params={"days": 7})
        assert r.status_code in (201, 422), (
            f"Esperado 201 (con datos) o 422 (sin datos), obtenido {r.status_code}"
        )

    def test_latest_returns_data_if_compute_succeeded(self, client):
        compute = client.post("/personality/compute", params={"days": 7})
        if compute.status_code == 422:
            pytest.skip("No hay suficientes interacciones para calcular personalidad")
        assert compute.status_code == 201

        r = client.get("/personality/metrics/latest")
        assert r.status_code == 200
        data = r.json()
        for field in ("sarcasm_level", "friendliness", "verbosity",
                      "technical_depth", "humor_frequency"):
            assert field in data, f"Falta campo '{field}' en respuesta"
            assert 0.0 <= data[field] <= 1.0

    def test_metrics_history_returns_list(self, client):
        r = client.get("/personality/metrics", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert "metrics" in data
        assert "count"   in data
        assert isinstance(data["metrics"], list)
