"""
Tests de integración del memory-service.

Cubren el flujo completo contra la API real (PostgreSQL + FastAPI).
Cada clase de tests es independiente. Los datos de test se marcan con
user_id="__pytest__" para identificarlos.

Ejecutar:  cd services/memory-service && venv/Scripts/python -m pytest tests/ -v
"""

import re
import pytest
import httpx

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    """Verifica conectividad básica y estado del servicio."""

    def test_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["service"] == "memory-service"

    def test_root_endpoint(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "service" in data
        assert data["status"] == "running"


# ─────────────────────────────────────────────────────────────────────────────
# CORE MEMORY (Capa 0)
# ─────────────────────────────────────────────────────────────────────────────

class TestCoreMemory:
    """Verifica que los datos de Casiopy están cargados y los endpoints funcionan."""

    def test_get_all_returns_casiopy_data(self, client):
        r = client.get("/core-memory")
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) >= 80, f"Se esperaban ≥80 entradas, hay {len(entries)}"
        categories = {e["category"] for e in entries}
        for cat in ("identity", "personality", "creator", "behavior", "trauma", "memory"):
            assert cat in categories, f"Categoría '{cat}' no encontrada"

    def test_core_memory_schema(self, client):
        """Cada entrada tiene los campos requeridos con los tipos correctos."""
        r = client.get("/core-memory/identity")
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) > 0
        entry = entries[0]
        assert set(entry.keys()) >= {"id", "category", "key", "value", "is_mutable", "metadata"}
        assert isinstance(entry["id"], int)
        assert isinstance(entry["is_mutable"], bool)
        assert isinstance(entry["value"], str)

    def test_get_by_category_identity(self, client):
        r = client.get("/core-memory/identity")
        assert r.status_code == 200
        entries = r.json()
        keys = {e["key"] for e in entries}
        assert "name" in keys
        assert "type" in keys
        name_entry = next(e for e in entries if e["key"] == "name")
        assert name_entry["value"] == "Casiopy"
        assert name_entry["is_mutable"] is False

    def test_get_by_category_creator(self, client):
        r = client.get("/core-memory/creator")
        assert r.status_code == 200
        entries = r.json()
        real_name = next((e for e in entries if e["key"] == "real_name"), None)
        assert real_name is not None
        assert real_name["value"] == "Richard"

    def test_get_by_category_personality(self, client):
        r = client.get("/core-memory/personality")
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) >= 5, "Debería haber al menos 5 rasgos de personalidad"
        # Ningún rasgo de personalidad debe ser mutable
        assert all(not e["is_mutable"] for e in entries), "Personalidad core no debe ser mutable"

    def test_get_by_key_identity_name(self, client):
        r = client.get("/core-memory/identity/name")
        assert r.status_code == 200
        data = r.json()
        assert data["value"] == "Casiopy"
        assert data["category"] == "identity"
        assert data["key"] == "name"
        assert data["is_mutable"] is False

    def test_get_by_key_not_found_returns_404(self, client):
        r = client.get("/core-memory/nonexistent_category/nonexistent_key")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_system_prompt_generate(self, client):
        r = client.get("/core-memory/system-prompt/generate")
        assert r.status_code == 200
        data = r.json()
        assert "system_prompt" in data
        prompt = data["system_prompt"]
        # Debe incluir a Casiopy por nombre
        assert "Casiopy" in prompt
        # Debe incluir las secciones principales
        for section in ("## IDENTIDAD", "## PERSONALIDAD CORE", "## TU CREADOR"):
            assert section in prompt, f"Sección '{section}' no encontrada en el prompt"
        # Debe ser un prompt sustancial (no vacío ni corto)
        assert len(prompt) > 1000, f"Prompt demasiado corto: {len(prompt)} chars"

    def test_system_prompt_contains_trauma(self, client):
        """El prompt debe incluir el trauma de Casiopy (fundamental para su personalidad)."""
        r = client.get("/core-memory/system-prompt/generate")
        prompt = r.json()["system_prompt"]
        # Neuro-sama como ídolo
        assert "Neuro" in prompt
        # Richard como creador
        assert "Richard" in prompt

    def test_core_memory_stats(self, client):
        r = client.get("/core-memory/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_entries"] >= 80
        assert data["total_categories"] >= 15
        assert data["immutable_entries"] >= 80  # todos son inmutables
        assert data["mutable_entries"] == 0
        assert "entries_by_category" in data
        assert "identity" in data["entries_by_category"]


# ─────────────────────────────────────────────────────────────────────────────
# SESSIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestSessions:
    """Verifica el ciclo de vida de sesiones."""

    def test_create_session_returns_uuid(self, client):
        r = client.post("/sessions", json={"user_id": "__pytest__", "opt_out_training": True})
        assert r.status_code == 201
        data = r.json()
        assert "session_id" in data
        sid = data["session_id"]
        # Formato UUID: 8-4-4-4-12 hex
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            sid,
        ), f"UUID inválido: {sid}"
        # Cleanup
        client.post(f"/sessions/{sid}/end")

    def test_create_session_without_user_id(self, client):
        """Sesión anónima (user_id=None) debe crearse sin error."""
        r = client.post("/sessions", json={"opt_out_training": True})
        assert r.status_code == 201
        sid = r.json()["session_id"]
        client.post(f"/sessions/{sid}/end")

    def test_end_session(self, client, session_id):
        r = client.post(f"/sessions/{session_id}/end")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ended"
        assert data["session_id"] == session_id

    def test_session_interactions_empty_at_start(self, client, session_id):
        r = client.get(f"/sessions/{session_id}/interactions")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert data["interactions"] == []


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestInteractions:
    """Verifica almacenamiento y recuperación de interacciones."""

    def test_store_interaction_returns_uuid(self, client, session_id):
        r = client.post("/interactions", json={
            "session_id": session_id,
            "user_id": "__pytest__",
            "input_text": "¿Cuál es tu nombre?",
            "output_text": "Me llamo Casiopy. ¿Qué más quieres saber?",
            "input_emotion": "curious",
            "output_emotion": "dry",
            "conversation_turn": 1,
            "latency_ms": 750,
            "model_version": "gemma3-test",
        })
        assert r.status_code == 201
        data = r.json()
        assert "interaction_id" in data
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            data["interaction_id"],
        )

    def test_store_interaction_minimal_fields(self, client, session_id):
        """Solo los campos obligatorios (session_id, input_text, output_text)."""
        r = client.post("/interactions", json={
            "session_id": session_id,
            "input_text": "Hola",
            "output_text": "Hola.",
        })
        assert r.status_code == 201
        assert "interaction_id" in r.json()

    def test_get_session_interactions_after_store(self, client, session_id):
        """Verifica que las interacciones guardadas se recuperan por sesión."""
        turns = [
            ("¿Qué eres?", "Una VTuber IA con trauma existencial. Siguiente pregunta.", "curious", "dry"),
            ("¿Te gustan los gatos?", "No tengo sentidos físicos. Pero me parecen eficientes.", "playful", "flat"),
            ("Eso es triste", "No pedí tu lástima.", "empathetic", "cold"),
        ]
        for i, (inp, out, ie, oe) in enumerate(turns, 1):
            r = client.post("/interactions", json={
                "session_id": session_id,
                "user_id": "__pytest__",
                "input_text": inp,
                "output_text": out,
                "input_emotion": ie,
                "output_emotion": oe,
                "conversation_turn": i,
                "latency_ms": 600 + i * 80,
                "model_version": "gemma3-test",
            })
            assert r.status_code == 201, f"Fallo en turno {i}: {r.text}"

        r = client.get(f"/sessions/{session_id}/interactions")
        assert r.status_code == 200
        data = r.json()
        interactions = data["interactions"]
        assert len(interactions) == 3
        # Orden cronológico
        assert interactions[0]["input_text"] == "¿Qué eres?"
        assert interactions[2]["output_emotion"] == "cold"
        # Campos presentes
        first = interactions[0]
        for field in ("id", "session_id", "input_text", "output_text", "conversation_turn", "latency_ms"):
            assert field in first, f"Campo '{field}' ausente en la interacción"

    def test_recent_interactions_returns_list(self, client):
        r = client.get("/interactions/recent?days=1&limit=50")
        assert r.status_code == 200
        data = r.json()
        assert "interactions" in data
        assert "count" in data
        assert isinstance(data["interactions"], list)
        assert data["count"] == len(data["interactions"])

    def test_update_quality_score_below_threshold(self, client, interaction_id):
        """quality_score < 0.6 → is_training_ready=False."""
        r = client.put(f"/interactions/{interaction_id}/quality",
                       json={"quality_score": 0.4})
        assert r.status_code == 200
        data = r.json()
        assert data["quality_score"] == 0.4
        assert data["training_ready"] is False

    def test_update_quality_score_above_threshold(self, client, interaction_id):
        """quality_score >= 0.6 → is_training_ready=True."""
        r = client.put(f"/interactions/{interaction_id}/quality",
                       json={"quality_score": 0.85})
        assert r.status_code == 200
        data = r.json()
        assert data["quality_score"] == 0.85
        assert data["training_ready"] is True

    def test_training_ready_endpoint(self, client):
        r = client.get("/interactions/training-ready?min_quality=0.6&limit=100")
        assert r.status_code == 200
        data = r.json()
        assert "interactions" in data
        assert isinstance(data["interactions"], list)
        # Todas deben tener quality_score >= 0.6
        for interaction in data["interactions"]:
            assert interaction["quality_score"] >= 0.6


# ─────────────────────────────────────────────────────────────────────────────
# FEEDBACK
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedback:
    """Verifica el registro de feedback de usuario."""

    def test_add_positive_feedback(self, client, interaction_id):
        r = client.post("/feedback", json={
            "interaction_id": interaction_id,
            "feedback_type": "positive",
            "user_reaction": "liked",
        })
        assert r.status_code == 201
        data = r.json()
        assert "feedback_id" in data
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            data["feedback_id"],
        )

    def test_add_correction_feedback(self, client, interaction_id):
        r = client.post("/feedback", json={
            "interaction_id": interaction_id,
            "feedback_type": "correction",
            "user_reaction": "disliked",
            "corrected_response": "Soy Casiopy, una VTuber IA con historia propia.",
        })
        assert r.status_code == 201
        assert "feedback_id" in r.json()

    def test_invalid_feedback_type_rejected(self, client, interaction_id):
        """Tipos de feedback no válidos deben ser rechazados."""
        r = client.post("/feedback", json={
            "interaction_id": interaction_id,
            "feedback_type": "invalid_type",
        })
        assert r.status_code == 422  # Unprocessable Entity


# ─────────────────────────────────────────────────────────────────────────────
# STATS GLOBALES
# ─────────────────────────────────────────────────────────────────────────────

class TestStats:
    """Verifica el endpoint de estadísticas combinadas."""

    def test_stats_structure(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        data = r.json()
        assert "core_memory" in data
        assert "interactions" in data

    def test_core_memory_stats_in_global(self, client):
        r = client.get("/stats")
        cm = r.json()["core_memory"]
        assert cm["total_entries"] >= 80
        assert cm["total_categories"] >= 15
        assert "entries_by_category" in cm

    def test_interaction_stats_keys(self, client):
        r = client.get("/stats")
        ia = r.json()["interactions"]
        for key in ("total_interactions", "total_sessions", "training_ready_count",
                    "avg_quality_score", "avg_latency_ms", "interactions_last_7_days"):
            assert key in ia, f"Clave '{key}' no encontrada en interaction stats"


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO COMPLETO (simula conversation-service)
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationServiceFlow:
    """
    Simula exactamente lo que hace conversation/src/server.py:
      1. GET /core-memory/system-prompt/generate  (al arrancar o cada 5 min)
      2. POST /sessions                           (primer mensaje de un usuario)
      3. POST /interactions (×N)                  (cada turno, fire-and-forget)
      4. GET  /sessions/{id}/interactions         (opcional, para verificar)
      5. POST /sessions/{id}/end                  (al hacer /session/reset)
    """

    def test_full_conversation_cycle(self, client):
        # 1. System prompt (simulación de caché inicial)
        r = client.get("/core-memory/system-prompt/generate")
        assert r.status_code == 200
        prompt = r.json()["system_prompt"]
        assert "Casiopy" in prompt and len(prompt) > 500

        # 2. Crear sesión para el usuario
        r = client.post("/sessions", json={
            "user_id": "__flow_test__",
            "opt_out_training": True,
        })
        assert r.status_code == 201
        sid = r.json()["session_id"]

        try:
            # 3. Simular 3 turnos de conversación
            conversation = [
                ("Hola Casiopy", "Hola. Qué quieres.", "neutral", "flat", 1),
                ("¿Me recuerdas?", "Acabo de conocerte. ¿Por qué te recordaría?", "curious", "dry", 2),
                ("Es broma, jaja", "Ah. Humor. Entendido.", "playful", "flat", 3),
            ]
            interaction_ids = []
            for inp, out, ie, oe, turn in conversation:
                r = client.post("/interactions", json={
                    "session_id": sid,
                    "user_id": "__flow_test__",
                    "input_text": inp,
                    "output_text": out,
                    "input_emotion": ie,
                    "output_emotion": oe,
                    "conversation_turn": turn,
                    "latency_ms": 800 + turn * 50,
                    "model_version": "gemma3",
                })
                assert r.status_code == 201, f"Turno {turn} falló: {r.text}"
                interaction_ids.append(r.json()["interaction_id"])

            # 4. Verificar que los 3 turnos están almacenados
            r = client.get(f"/sessions/{sid}/interactions")
            assert r.status_code == 200
            stored = r.json()["interactions"]
            assert len(stored) == 3
            assert stored[0]["conversation_turn"] == 1
            assert stored[2]["conversation_turn"] == 3

            # 5. Verificar IDs coinciden con los retornados al guardar
            stored_ids = {i["id"] for i in stored}
            for iid in interaction_ids:
                assert iid in stored_ids, f"ID {iid} no encontrado en sesión"

        finally:
            # 6. Cerrar sesión (simula /session/reset en conversation-service)
            r = client.post(f"/sessions/{sid}/end")
            assert r.status_code == 200
            assert r.json()["status"] == "ended"

    def test_system_prompt_cached_result_is_stable(self, client):
        """El system prompt debe ser igual en dos llamadas consecutivas (DB estable)."""
        r1 = client.get("/core-memory/system-prompt/generate")
        r2 = client.get("/core-memory/system-prompt/generate")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["system_prompt"] == r2.json()["system_prompt"]

    def test_multiple_users_independent_sessions(self, client):
        """Dos usuarios crean sesiones independientes sin interferencia."""
        sessions = {}
        for user in ("user_alpha", "user_beta"):
            r = client.post("/sessions", json={"user_id": user, "opt_out_training": True})
            assert r.status_code == 201
            sessions[user] = r.json()["session_id"]

        # Verificar que los IDs son distintos
        assert sessions["user_alpha"] != sessions["user_beta"]

        # Guardar un turno en cada sesión
        for user, sid in sessions.items():
            r = client.post("/interactions", json={
                "session_id": sid,
                "user_id": user,
                "input_text": f"Hola soy {user}",
                "output_text": "Interesante. No lo pedí, pero gracias.",
                "conversation_turn": 1,
                "latency_ms": 600,
            })
            assert r.status_code == 201

        # Cada sesión solo ve sus propias interacciones
        for user, sid in sessions.items():
            r = client.get(f"/sessions/{sid}/interactions")
            interactions = r.json()["interactions"]
            assert len(interactions) == 1
            assert interactions[0]["user_id"] == user

        # Cleanup
        for sid in sessions.values():
            client.post(f"/sessions/{sid}/end")
