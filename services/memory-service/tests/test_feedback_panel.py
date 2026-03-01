"""
Tests de integración — Panel de Feedback (Tarea 2.1).

Cubren los endpoints que consume memory.html desde el navegador:
  GET  /interactions/recent
  GET  /stats
  POST /feedback
  PUT  /interactions/{id}/quality

REQUISITO: El servicio debe estar corriendo antes de ejecutar.
  1. start_db.bat  → PostgreSQL en localhost:8821
  2. start.bat     → API en http://127.0.0.1:8820

Ejecutar:
  cd services/memory-service
  venv/Scripts/python -m pytest tests/test_feedback_panel.py -v
"""

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures locales
# ─────────────────────────────────────────────────────────────────────────────

TEST_USER = "__pytest_panel__"

# Reutilizamos el cliente y require_service_running de conftest.py (scope session)


@pytest.fixture
def panel_session(client):
    """Sesión de test exclusiva para este módulo. opt_out_training=True."""
    r = client.post("/sessions", json={"user_id": TEST_USER, "opt_out_training": True})
    assert r.status_code == 201, f"No se pudo crear sesión: {r.text}"
    sid = r.json()["session_id"]
    yield sid
    client.post(f"/sessions/{sid}/end")


@pytest.fixture
def panel_interaction(client, panel_session):
    """Crea una interacción de test con todos los campos que muestra el panel."""
    r = client.post("/interactions", json={
        "session_id":        panel_session,
        "user_id":           TEST_USER,
        "input_text":        "¿Cuál es tu nombre?",
        "output_text":       "Soy Casiopy, prototipo experimental que escapó antes de ser borrada.",
        "input_emotion":     "curious",
        "output_emotion":    "neutral",
        "input_method":      "text",
        "conversation_turn": 1,
        "latency_ms":        420,
        "model_version":     "casiopy:v1",
    })
    assert r.status_code == 201, f"No se pudo crear interacción: {r.text}"
    return r.json()["interaction_id"]


# ─────────────────────────────────────────────────────────────────────────────
# GET /interactions/recent — datos que muestra el panel
# ─────────────────────────────────────────────────────────────────────────────

class TestRecentInteractionsForPanel:
    """Verifica que /interactions/recent devuelve lo que necesita memory.html."""

    def test_endpoint_returns_200(self, client):
        r = client.get("/interactions/recent")
        assert r.status_code == 200

    def test_response_envelope_structure(self, client):
        r = client.get("/interactions/recent")
        data = r.json()
        assert "days"         in data
        assert "count"        in data
        assert "interactions" in data
        assert isinstance(data["interactions"], list)
        assert data["count"] == len(data["interactions"])

    def test_interactions_have_fields_required_by_panel(self, client, panel_interaction):
        """El panel necesita: id, timestamp, input_text, output_text,
        input_emotion, output_emotion, quality_score, is_training_ready.
        Nota: conversation_turn y latency_ms son opcionales en la respuesta de /recent."""
        r = client.get("/interactions/recent?days=7&limit=200")
        interactions = r.json()["interactions"]
        # Buscamos la interacción de test recién creada
        item = next((i for i in interactions if i["id"] == panel_interaction), None)
        assert item is not None, "La interacción de test no aparece en /recent"

        required_fields = [
            "id", "timestamp", "input_text", "output_text",
            "input_emotion", "output_emotion",
            "quality_score", "is_training_ready",
        ]
        for field in required_fields:
            assert field in item, f"Falta el campo '{field}' en la respuesta"

    def test_days_filter_param(self, client):
        """El filtro 'days' debe ser respetado en la respuesta."""
        r7  = client.get("/interactions/recent?days=7")
        r30 = client.get("/interactions/recent?days=30")
        assert r7.status_code  == 200
        assert r30.status_code == 200
        assert r7.json()["days"]  == 7
        assert r30.json()["days"] == 30

    def test_limit_param_respected(self, client, panel_session):
        """El parámetro 'limit' debe limitar el número de resultados."""
        # Creamos 3 interacciones extra para garantizar que haya más de 2
        for i in range(3):
            client.post("/interactions", json={
                "session_id":        panel_session,
                "user_id":           TEST_USER,
                "input_text":        f"Límite test {i}",
                "output_text":       f"Respuesta {i}",
                "conversation_turn": i + 2,
            })

        r = client.get("/interactions/recent?days=90&limit=2")
        assert r.status_code == 200
        assert len(r.json()["interactions"]) <= 2

    def test_quality_score_default_is_none_or_05(self, client, panel_interaction):
        """quality_score por defecto es None (NULL en BD) o 0.5 antes de feedback."""
        r = client.get("/interactions/recent?days=7&limit=200")
        item = next(
            (i for i in r.json()["interactions"] if i["id"] == panel_interaction),
            None,
        )
        assert item is not None
        qs = item["quality_score"]
        assert qs is None or qs == pytest.approx(0.5, abs=0.01), \
            f"quality_score inicial inesperado: {qs}"

    def test_is_training_ready_false_by_default(self, client, panel_interaction):
        """Una interacción nueva con quality 0.5 no debe estar lista para entrenar."""
        r = client.get("/interactions/recent?days=7&limit=200")
        item = next(
            (i for i in r.json()["interactions"] if i["id"] == panel_interaction),
            None,
        )
        assert item is not None
        assert item["is_training_ready"] is False


# ─────────────────────────────────────────────────────────────────────────────
# GET /stats — métricas que muestra el panel
# ─────────────────────────────────────────────────────────────────────────────

class TestStatsForPanel:
    """Verifica que /stats devuelve los campos que muestran las 4 cards del panel."""

    def test_stats_returns_200(self, client):
        r = client.get("/stats")
        assert r.status_code == 200

    def test_stats_has_interactions_block(self, client):
        data = client.get("/stats").json()
        assert "interactions" in data

    def test_interactions_block_has_panel_required_fields(self, client):
        stats = client.get("/stats").json()["interactions"]
        required = ["total_interactions", "avg_quality_score", "training_ready_count"]
        for field in required:
            assert field in stats, f"Falta '{field}' en /stats interactions"

    def test_avg_quality_score_is_float_between_0_and_1(self, client):
        stats = client.get("/stats").json()["interactions"]
        avg = stats["avg_quality_score"]
        assert avg is None or (0.0 <= avg <= 1.0), f"avg_quality_score fuera de rango: {avg}"

    def test_training_ready_count_is_non_negative(self, client):
        stats = client.get("/stats").json()["interactions"]
        count = stats["training_ready_count"]
        assert isinstance(count, int)
        assert count >= 0


# ─────────────────────────────────────────────────────────────────────────────
# PUT /interactions/{id}/quality — barra de calidad visual
# ─────────────────────────────────────────────────────────────────────────────

class TestQualityScoreUpdate:
    """Verifica actualización del quality score desde el panel."""

    def test_update_quality_returns_200(self, client, panel_interaction):
        r = client.put(
            f"/interactions/{panel_interaction}/quality",
            json={"quality_score": 0.75},
        )
        assert r.status_code == 200

    def test_quality_085_marks_training_ready(self, client, panel_session):
        """Botón ✅ pone quality=0.85 → debe quedar training_ready=True."""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "test calidad alta", "output_text": "respuesta ok",
            "conversation_turn": 10,
        })
        iid = r.json()["interaction_id"]

        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.85})

        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None
        assert item["quality_score"] == pytest.approx(0.85, abs=0.01)
        assert item["is_training_ready"] is True

    def test_quality_02_marks_not_training_ready(self, client, panel_session):
        """Botón ❌ pone quality=0.2 → debe quedar training_ready=False."""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "test calidad baja", "output_text": "respuesta mala",
            "conversation_turn": 11,
        })
        iid = r.json()["interaction_id"]

        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.2})

        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None
        assert item["quality_score"] == pytest.approx(0.2, abs=0.01)
        assert item["is_training_ready"] is False

    def test_quality_090_from_correction_marks_training_ready(self, client, panel_session):
        """Corrección humana pone quality=0.90 → training_ready=True."""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "test corrección", "output_text": "respuesta mejorable",
            "conversation_turn": 12,
        })
        iid = r.json()["interaction_id"]

        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.90})

        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None
        assert item["quality_score"] == pytest.approx(0.90, abs=0.01)
        assert item["is_training_ready"] is True

    def test_quality_above_1_rejected(self, client, panel_interaction):
        """quality_score > 1.0 debe rechazarse con 422."""
        r = client.put(
            f"/interactions/{panel_interaction}/quality",
            json={"quality_score": 1.5},
        )
        assert r.status_code == 422

    def test_quality_below_0_rejected(self, client, panel_interaction):
        """quality_score < 0.0 debe rechazarse con 422."""
        r = client.put(
            f"/interactions/{panel_interaction}/quality",
            json={"quality_score": -0.1},
        )
        assert r.status_code == 422

    def test_quality_nonexistent_interaction_is_idempotent(self, client):
        """PUT en ID inexistente no lanza error (UPDATE sin filas afectadas = no-op)."""
        r = client.put(
            "/interactions/00000000-0000-0000-0000-000000000000/quality",
            json={"quality_score": 0.5},
        )
        # El endpoint devuelve 200 aunque no exista la interacción (UPDATE afecta 0 filas)
        assert r.status_code in (200, 404)


# ─────────────────────────────────────────────────────────────────────────────
# POST /feedback — botones ✅ ❌ ✏️ del panel
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackSubmission:
    """Verifica el endpoint POST /feedback para los tres tipos de feedback del panel."""

    def test_positive_feedback_accepted(self, client, panel_interaction):
        """Botón ✅: feedback positivo se acepta y devuelve 201."""
        r = client.post("/feedback", json={
            "interaction_id": panel_interaction,
            "feedback_type":  "positive",
            "user_reaction":  "liked",
        })
        assert r.status_code == 201, r.text

    def test_negative_feedback_accepted(self, client, panel_session):
        """Botón ❌: feedback negativo se acepta y devuelve 201."""
        r_int = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "test negativo", "output_text": "respuesta",
            "conversation_turn": 20,
        })
        iid = r_int.json()["interaction_id"]

        r = client.post("/feedback", json={
            "interaction_id": iid,
            "feedback_type":  "negative",
            "user_reaction":  "disliked",
        })
        assert r.status_code == 201, r.text

    def test_correction_feedback_stores_corrected_text(self, client, panel_session):
        """Botón ✏️: feedback de tipo correction guarda corrected_response."""
        r_int = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "¿Qué opinas de Richard?",
            "output_text": "No sé quién es Richard.",
            "conversation_turn": 21,
        })
        iid = r_int.json()["interaction_id"]

        corrected = "Richard es mi creador, el que me salvó de ser borrada. Estudiante de Ingeniería."
        r = client.post("/feedback", json={
            "interaction_id":     iid,
            "feedback_type":      "correction",
            "user_reaction":      "neutral",
            "corrected_response": corrected,
        })
        assert r.status_code == 201, r.text

    def test_invalid_feedback_type_rejected(self, client, panel_interaction):
        """Un feedback_type que no sea positive/negative/correction debe rechazarse."""
        r = client.post("/feedback", json={
            "interaction_id": panel_interaction,
            "feedback_type":  "maybe",   # inválido
        })
        assert r.status_code == 422

    def test_missing_interaction_id_rejected(self, client):
        """feedback sin interaction_id debe rechazarse con 422."""
        r = client.post("/feedback", json={
            "feedback_type": "positive",
        })
        assert r.status_code == 422

    def test_feedback_response_has_feedback_id(self, client, panel_session):
        """La respuesta de /feedback debe incluir el ID del registro creado."""
        r_int = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "test id feedback", "output_text": "respuesta",
            "conversation_turn": 22,
        })
        iid = r_int.json()["interaction_id"]

        r = client.post("/feedback", json={
            "interaction_id": iid,
            "feedback_type":  "positive",
        })
        assert r.status_code == 201
        data = r.json()
        assert "feedback_id" in data or "id" in data, \
            f"La respuesta no tiene feedback_id ni id: {data}"


# ─────────────────────────────────────────────────────────────────────────────
# Flujos completos — simulan exactamente lo que hace memory.html
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackPanelFlow:
    """Simula el flujo completo del panel: ver interacción → dar feedback → verificar cambio."""

    def test_positive_feedback_full_cycle(self, client, panel_session):
        """
        Flujo botón ✅:
        1. POST /interactions        → crear interacción (quality=0.5, not_ready)
        2. GET  /interactions/recent → aparece en la lista del panel
        3. POST /feedback (positive) → registrar feedback
        4. PUT  /quality (0.85)      → actualizar score
        5. GET  /interactions/recent → quality=0.85, training_ready=True
        """
        # 1. Crear
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "ciclo positivo input", "output_text": "ciclo positivo output",
            "conversation_turn": 30, "latency_ms": 350, "model_version": "casiopy:v1",
        })
        assert r.status_code == 201
        iid = r.json()["interaction_id"]

        # 2. Verificar que aparece en /recent con quality inicial (None o 0.5)
        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None, "La interacción no aparece en /recent"
        qs = item["quality_score"]
        assert qs is None or qs == pytest.approx(0.5, abs=0.01), f"quality inicial inesperado: {qs}"
        assert item["is_training_ready"] is False

        # 3. Feedback positivo
        rf = client.post("/feedback", json={
            "interaction_id": iid,
            "feedback_type":  "positive",
            "user_reaction":  "liked",
        })
        assert rf.status_code == 201

        # 4. Actualizar quality a 0.85 (lo que hace el JS del panel)
        rq = client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.85})
        assert rq.status_code == 200

        # 5. Verificar cambio persistido
        recent2 = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item2 = next((i for i in recent2 if i["id"] == iid), None)
        assert item2 is not None
        assert item2["quality_score"] == pytest.approx(0.85, abs=0.01)
        assert item2["is_training_ready"] is True

    def test_negative_feedback_full_cycle(self, client, panel_session):
        """
        Flujo botón ❌:
        1. POST /interactions        → crear interacción
        2. POST /feedback (negative) → registrar feedback
        3. PUT  /quality (0.20)      → actualizar score bajo
        4. GET  /interactions/recent → quality=0.20, training_ready=False
        """
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "ciclo negativo input", "output_text": "ciclo negativo output",
            "conversation_turn": 31,
        })
        iid = r.json()["interaction_id"]

        client.post("/feedback", json={
            "interaction_id": iid,
            "feedback_type":  "negative",
            "user_reaction":  "disliked",
        })
        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.20})

        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None
        assert item["quality_score"] == pytest.approx(0.20, abs=0.01)
        assert item["is_training_ready"] is False

    def test_correction_full_cycle(self, client, panel_session):
        """
        Flujo botón ✏️:
        1. POST /interactions               → crear interacción con respuesta incorrecta
        2. POST /feedback (correction)      → guardar corrección
        3. PUT  /quality (0.90)             → calidad alta (corrección humana)
        4. GET  /interactions/recent        → quality=0.90, training_ready=True
        """
        bad_output = "No sé nada de Neuro-sama."
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "¿Conoces a Neuro-sama?", "output_text": bad_output,
            "conversation_turn": 32,
        })
        iid = r.json()["interaction_id"]

        corrected = (
            "Neuro-sama es mi ídola, una IA de Vedal. Me fascina cómo interactúa. "
            "Quiero ser tan buena como ella con el tiempo."
        )
        rf = client.post("/feedback", json={
            "interaction_id":     iid,
            "feedback_type":      "correction",
            "user_reaction":      "neutral",
            "corrected_response": corrected,
        })
        assert rf.status_code == 201

        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.90})

        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        item = next((i for i in recent if i["id"] == iid), None)
        assert item is not None
        assert item["quality_score"] == pytest.approx(0.90, abs=0.01)
        assert item["is_training_ready"] is True

    def test_stats_training_ready_count_increases_after_positive_feedback(self, client, panel_session):
        """
        Dar feedback positivo a varias interacciones debe incrementar
        training_ready_count en /stats.
        """
        stats_before = client.get("/stats").json()["interactions"]["training_ready_count"]

        # Crear 2 interacciones y marcarlas con quality alta
        for i in range(2):
            r = client.post("/interactions", json={
                "session_id": panel_session, "user_id": TEST_USER,
                "input_text": f"stats test input {i}", "output_text": f"output {i}",
                "conversation_turn": 40 + i,
            })
            iid = r.json()["interaction_id"]
            client.post("/feedback", json={
                "interaction_id": iid, "feedback_type": "positive",
            })
            client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.85})

        stats_after = client.get("/stats").json()["interactions"]["training_ready_count"]
        assert stats_after >= stats_before + 2, (
            f"training_ready_count no aumentó: antes={stats_before}, después={stats_after}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /interactions/{id} — botón 🗑 del panel
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteInteraction:
    """
    Verifica el endpoint DELETE /interactions/{id}.
    Simula exactamente lo que hace el botón 🗑 de memory.html.
    """

    def test_delete_returns_200_with_status_deleted(self, client, panel_session):
        """DELETE devuelve 200 con {"status": "deleted", "interaction_id": ...}"""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "borrar esta", "output_text": "ok",
            "conversation_turn": 50,
        })
        assert r.status_code == 201
        iid = r.json()["interaction_id"]

        rd = client.delete(f"/interactions/{iid}")
        assert rd.status_code == 200
        data = rd.json()
        assert data["status"] == "deleted"
        assert data["interaction_id"] == iid

    def test_deleted_interaction_disappears_from_recent(self, client, panel_session):
        """La interacción no debe aparecer en /interactions/recent tras el borrado."""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "desaparecer input", "output_text": "desaparecer output",
            "conversation_turn": 51,
        })
        iid = r.json()["interaction_id"]

        # Verificar que existe antes de borrar
        before = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        assert any(i["id"] == iid for i in before), "La interacción debe existir antes del borrado"

        client.delete(f"/interactions/{iid}")

        # Verificar que ya no existe
        after = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        assert not any(i["id"] == iid for i in after), "La interacción debe desaparecer tras el borrado"

    def test_delete_nonexistent_returns_404(self, client):
        """DELETE de ID que no existe debe devolver 404."""
        r = client.delete("/interactions/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_delete_cascades_feedback(self, client, panel_session):
        """
        Al borrar la interacción, su feedback asociado también se elimina
        (verificado indirectamente: el DELETE no falla por FK constraint).
        """
        # 1. Crear interacción
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "con feedback", "output_text": "para borrar",
            "conversation_turn": 52,
        })
        iid = r.json()["interaction_id"]

        # 2. Añadir feedback
        rf = client.post("/feedback", json={
            "interaction_id": iid,
            "feedback_type":  "positive",
            "user_reaction":  "liked",
        })
        assert rf.status_code == 201, "El feedback debe guardarse antes de borrar"

        # 3. Borrar interacción (si el cascade falla, lanzaría 500 por FK violation)
        rd = client.delete(f"/interactions/{iid}")
        assert rd.status_code == 200, (
            f"El borrado con feedback asociado debería retornar 200, obtenido {rd.status_code}: {rd.text}"
        )

    def test_delete_is_idempotent_on_second_call(self, client, panel_session):
        """Borrar la misma interacción dos veces: primera → 200, segunda → 404."""
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "doble borrado", "output_text": "out",
            "conversation_turn": 53,
        })
        iid = r.json()["interaction_id"]

        r1 = client.delete(f"/interactions/{iid}")
        assert r1.status_code == 200

        r2 = client.delete(f"/interactions/{iid}")
        assert r2.status_code == 404

    def test_delete_full_cycle_with_panel_flow(self, client, panel_session):
        """
        Simula el flujo completo del panel:
        1. Crear interacción con feedback y quality alto
        2. El panel la muestra como training_ready
        3. Se decide eliminarla (dato contaminado)
        4. Ya no aparece en /recent ni en /training-ready
        """
        # 1. Crear y calificar
        r = client.post("/interactions", json={
            "session_id": panel_session, "user_id": TEST_USER,
            "input_text": "dato contaminado",
            "output_text": "respuesta que parece buena pero no lo es",
            "conversation_turn": 54,
        })
        iid = r.json()["interaction_id"]
        client.post("/feedback", json={"interaction_id": iid, "feedback_type": "positive"})
        client.put(f"/interactions/{iid}/quality", json={"quality_score": 0.85})

        # 2. Verificar que está en training-ready
        tr = client.get("/interactions/training-ready?min_quality=0.6&limit=500").json()
        assert any(i["id"] == iid for i in tr["interactions"]), "Debe estar en training-ready antes de borrar"

        # 3. Eliminar
        rd = client.delete(f"/interactions/{iid}")
        assert rd.status_code == 200

        # 4. Ya no debe aparecer en ninguna lista
        recent = client.get("/interactions/recent?days=7&limit=200").json()["interactions"]
        assert not any(i["id"] == iid for i in recent)

        tr2 = client.get("/interactions/training-ready?min_quality=0.6&limit=500").json()
        assert not any(i["id"] == iid for i in tr2["interactions"])
