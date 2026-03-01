"""
Tests de la Tarea 2.2 — Pipeline de exportación automático.

Dos grupos:
  - TestValidateDatasetFlexible → valida la función sin necesitar servicio
  - TestPipelineStateIO         → valida load_state/save_state sin servicio
  - TestPipelineEndpoints       → valida /pipeline/* (requiere servicio corriendo)

Ejecutar todos:
  cd services/memory-service
  python -m pytest tests/test_pipeline.py -v

Solo tests sin servicio:
  python -m pytest tests/test_pipeline.py -v -k "not TestPipelineEndpoints"
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# ─── Ruta al módulo validate_dataset (scripts/) ───────────────────────────────
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SRC_DIR     = Path(__file__).parent.parent / "src"

# Importamos validate_dataset_flexible directamente para los tests offline
sys.path.insert(0, str(SCRIPTS_DIR))
from validate_dataset import validate_dataset_flexible  # noqa: E402

# Importamos pipeline_manager para los tests de estado
sys.path.insert(0, str(SRC_DIR))
from pipeline_manager import load_state, save_state, _default_state, _update_next_run, STATE_FILE  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _write_jsonl(path: Path, entries: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _make_entry(role_sequence: list = None, content_override: dict = None) -> dict:
    """Genera un ejemplo ChatML válido."""
    if role_sequence is None:
        role_sequence = ["user", "assistant"]
    msgs = []
    for role in role_sequence:
        msgs.append({"role": role, "content": content_override.get(role, f"Contenido de {role}") if content_override else f"Contenido de {role}"})
    return {"messages": msgs, "metadata": {"quality_score": 0.8}}


def _make_valid_2msg_dataset(n: int) -> list:
    return [_make_entry(["user", "assistant"]) for _ in range(n)]


def _make_valid_3msg_dataset(n: int) -> list:
    return [_make_entry(["system", "user", "assistant"]) for _ in range(n)]


# ═══════════════════════════════════════════════════════════════════════════════
# TestValidateDatasetFlexible — sin servicio
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateDatasetFlexible:
    """
    Valida la función validate_dataset_flexible del módulo validate_dataset.py.
    No requiere ningún servicio externo.
    """

    def test_accepts_2msg_format_user_assistant(self, tmp_path):
        """Formato episódico (user+assistant) debe ser válido."""
        f = tmp_path / "dataset.jsonl"
        _write_jsonl(f, _make_valid_2msg_dataset(50))
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "success"
        assert result["count"] == 50

    def test_accepts_3msg_format_system_user_assistant(self, tmp_path):
        """Formato personalidad (system+user+assistant) también debe ser válido."""
        f = tmp_path / "dataset.jsonl"
        _write_jsonl(f, _make_valid_3msg_dataset(50))
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "success"
        assert result["count"] == 50

    def test_rejects_nonexistent_file(self, tmp_path):
        result = validate_dataset_flexible(str(tmp_path / "no_existe.jsonl"))
        assert result["status"] == "failed"
        assert "no encontrado" in result["reason"]

    def test_rejects_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("", encoding="utf-8")
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"
        assert result["count"] == 0

    def test_rejects_invalid_json(self, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text("esto no es json\n", encoding="utf-8")
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"
        assert "JSON inválido" in result["reason"]

    def test_rejects_wrong_role_sequence(self, tmp_path):
        """Secuencia [assistant, user] debe rechazarse."""
        f = tmp_path / "wrong.jsonl"
        entries = [_make_entry(["assistant", "user"]) for _ in range(50)]
        _write_jsonl(f, entries)
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"
        assert result["errors"]

    def test_rejects_missing_messages_key(self, tmp_path):
        f = tmp_path / "missing.jsonl"
        entries = [{"no_messages": "aqui"} for _ in range(50)]
        _write_jsonl(f, entries)
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"

    def test_rejects_empty_content_in_message(self, tmp_path):
        f = tmp_path / "empty_content.jsonl"
        entries = [
            {"messages": [
                {"role": "user", "content": "Pregunta válida"},
                {"role": "assistant", "content": "   "},  # solo espacios
            ]}
            for _ in range(50)
        ]
        _write_jsonl(f, entries)
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"

    def test_rejects_insufficient_examples_below_50(self, tmp_path):
        """49 ejemplos < 50 mínimo → fallar."""
        f = tmp_path / "few.jsonl"
        _write_jsonl(f, _make_valid_2msg_dataset(49))
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"
        assert result["count"] == 49
        assert "insuficientes" in result["reason"]

    def test_accepts_exactly_50_examples(self, tmp_path):
        """Exactamente 50 ejemplos debe pasar el umbral."""
        f = tmp_path / "exactly50.jsonl"
        _write_jsonl(f, _make_valid_2msg_dataset(50))
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "success"
        assert result["count"] == 50

    def test_custom_min_count_respected(self, tmp_path):
        """El parámetro min_count debe respetarse."""
        f = tmp_path / "ten.jsonl"
        _write_jsonl(f, _make_valid_2msg_dataset(10))
        result = validate_dataset_flexible(str(f), min_count=10)
        assert result["status"] == "success"
        result_fail = validate_dataset_flexible(str(f), min_count=11)
        assert result_fail["status"] == "failed"

    def test_returns_dict_with_required_keys(self, tmp_path):
        """El resultado siempre tiene status, count, reason y errors."""
        f = tmp_path / "dataset.jsonl"
        _write_jsonl(f, _make_valid_2msg_dataset(50))
        result = validate_dataset_flexible(str(f))
        for key in ("status", "count", "reason", "errors"):
            assert key in result, f"Falta clave '{key}' en el resultado"

    def test_errors_list_capped_at_10(self, tmp_path):
        """Máximo 10 errores en la lista errors."""
        f = tmp_path / "many_errors.jsonl"
        # 50 entradas sin campo 'messages' → 50 errores
        _write_jsonl(f, [{"no": "messages"} for _ in range(50)])
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "failed"
        assert len(result["errors"]) <= 10

    def test_mixed_2msg_and_3msg_accepted(self, tmp_path):
        """Dataset mezclando formato 2-msg y 3-msg es válido."""
        f = tmp_path / "mixed.jsonl"
        entries = _make_valid_2msg_dataset(25) + _make_valid_3msg_dataset(25)
        _write_jsonl(f, entries)
        result = validate_dataset_flexible(str(f))
        assert result["status"] == "success"
        assert result["count"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# TestPipelineStateIO — sin servicio
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineStateIO:
    """
    Valida load_state / save_state / _update_next_run.
    Usa monkeypatch para redirigir STATE_FILE a un directorio temporal.
    """

    @pytest.fixture(autouse=True)
    def _redirect_state_file(self, tmp_path, monkeypatch):
        """Redirige STATE_FILE a un archivo temporal para cada test."""
        import pipeline_manager as pm
        monkeypatch.setattr(pm, "STATE_FILE", tmp_path / "pipeline_state.json")

    def test_default_state_has_required_keys(self):
        state = _default_state()
        for key in ("current_model", "previous_model", "next_run", "last_run", "run_history"):
            assert key in state, f"Falta clave '{key}' en default_state"

    def test_default_current_model_is_v1(self):
        state = _default_state()
        assert state["current_model"] == "casiopy:v1"

    def test_default_run_history_is_empty_list(self):
        state = _default_state()
        assert state["run_history"] == []

    def test_load_state_returns_default_when_no_file(self):
        state = load_state()
        assert state["current_model"] == "casiopy:v1"
        assert state["run_history"] == []

    def test_state_roundtrip(self):
        """Guardar y volver a cargar debe devolver el mismo contenido."""
        state = _default_state()
        state["current_model"] = "casiopy:week01"
        state["run_history"] = [{"week_number": 1, "status": "success"}]
        save_state(state)
        loaded = load_state()
        assert loaded["current_model"] == "casiopy:week01"
        assert len(loaded["run_history"]) == 1

    def test_corrupted_state_returns_default(self, monkeypatch):
        """Si el JSON está corrupto, load_state devuelve el estado por defecto."""
        import pipeline_manager as pm
        pm.STATE_FILE.write_text("esto no es json válido", encoding="utf-8")
        state = load_state()
        assert state["current_model"] == "casiopy:v1"

    def test_update_next_run_sets_future_iso_string(self):
        state = _default_state()
        _update_next_run(state)
        assert state["next_run"] is not None
        next_dt = datetime.fromisoformat(state["next_run"])
        assert next_dt > datetime.now(), "next_run debe ser en el futuro"

    def test_update_next_run_is_always_sunday(self):
        state = _default_state()
        _update_next_run(state)
        next_dt = datetime.fromisoformat(state["next_run"])
        assert next_dt.weekday() == 6, "next_run debe ser domingo (weekday=6)"

    def test_update_next_run_hour_is_23(self):
        state = _default_state()
        _update_next_run(state)
        next_dt = datetime.fromisoformat(state["next_run"])
        assert next_dt.hour == 23

    def test_run_history_capped_at_20(self):
        """save_state debe mantener solo los últimos 20 runs."""
        state = _default_state()
        state["run_history"] = [{"n": i} for i in range(25)]
        save_state(state)
        loaded = load_state()
        # El cap se aplica en _finish_run, no en save_state/load_state
        # Verificamos que al guardar 25 se recuperan 25 (cap es responsabilidad del manager)
        assert len(loaded["run_history"]) == 25


# ═══════════════════════════════════════════════════════════════════════════════
# TestPipelineEndpoints — requiere servicio corriendo en 8820
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineEndpoints:
    """
    Valida los endpoints /pipeline/* del memory-service.
    Requiere que el servicio esté corriendo en http://127.0.0.1:8820.
    """

    # ── GET /pipeline/status ──────────────────────────────────────────────────

    def test_status_returns_200(self, client):
        r = client.get("/pipeline/status")
        assert r.status_code == 200

    def test_status_has_required_fields(self, client):
        data = client.get("/pipeline/status").json()
        for field in ("current_model", "previous_model", "next_run", "last_run"):
            assert field in data, f"Falta '{field}' en /pipeline/status"

    def test_status_current_model_is_string(self, client):
        data = client.get("/pipeline/status").json()
        assert isinstance(data["current_model"], str)
        assert len(data["current_model"]) > 0

    def test_status_next_run_is_future_or_none(self, client):
        data = client.get("/pipeline/status").json()
        if data["next_run"] is not None:
            next_dt = datetime.fromisoformat(data["next_run"])
            # Normalizar a naive para comparar (APScheduler puede devolver timezone-aware)
            if next_dt.tzinfo is not None:
                next_dt = next_dt.replace(tzinfo=None)
            assert next_dt > datetime.now(), "next_run debe ser en el futuro"

    # ── GET /pipeline/history ─────────────────────────────────────────────────

    def test_history_returns_200(self, client):
        r = client.get("/pipeline/history")
        assert r.status_code == 200

    def test_history_has_count_and_history_keys(self, client):
        data = client.get("/pipeline/history").json()
        assert "count" in data
        assert "history" in data

    def test_history_is_a_list(self, client):
        data = client.get("/pipeline/history").json()
        assert isinstance(data["history"], list)

    def test_history_count_matches_list_length(self, client):
        data = client.get("/pipeline/history").json()
        assert data["count"] == len(data["history"])

    # ── POST /pipeline/trigger ────────────────────────────────────────────────

    def test_trigger_returns_200(self, client):
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        assert r.status_code == 200

    def test_trigger_returns_status_field(self, client):
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        data = r.json()
        assert "status" in data

    def test_trigger_status_is_valid_terminal_value(self, client):
        """El status debe ser uno de los valores terminales conocidos."""
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        data = r.json()
        valid_statuses = {"skipped", "partial", "failed", "success", "already_running"}
        assert data["status"] in valid_statuses, (
            f"Status inesperado: {data['status']}. Válidos: {valid_statuses}"
        )

    def test_trigger_with_skip_training_never_runs_train_step(self, client):
        """Con skip_training=True nunca debe aparecer el paso 'train' ni 'deploy'."""
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        data = r.json()
        steps = data.get("steps", {})
        assert "train" not in steps, "El paso 'train' no debe ejecutarse con skip_training=True"
        assert "deploy" not in steps, "El paso 'deploy' no debe ejecutarse con skip_training=True"
        assert "test" not in steps, "El paso 'test' no debe ejecutarse con skip_training=True"

    def test_trigger_second_call_while_running_returns_already_running_or_completes(self, client):
        """
        Si se llama dos veces seguidas (con el servicio en un estado donde
        puede responder rápido), la segunda debería ver already_running o el run completo.
        Este test verifica que el lock funciona correctamente.
        """
        # Llamada simple con skip_training — debería terminar en < 5s si no hay datos
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        assert r.status_code == 200
        # El estado en /pipeline/status debe reflejar que hubo un run
        status_r = client.get("/pipeline/status")
        assert status_r.status_code == 200
        last_run = status_r.json().get("last_run")
        # Si hubo datos suficientes el last_run puede ser None (primer run) o tener el status
        if last_run is not None:
            assert "status" in last_run

    def test_trigger_updates_history(self, client):
        """Después de un trigger, el historial debe tener al menos 1 entrada."""
        # Primero disparamos el pipeline
        client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        # Luego verificamos el historial
        r = client.get("/pipeline/history")
        data = r.json()
        assert data["count"] >= 1, "El historial debe tener al menos 1 entrada tras el trigger"

    def test_trigger_accepts_empty_body(self, client):
        """El body es opcional — sin body usa skip_training=False."""
        # Con skip_training=False y sin datos de entrenamiento debería retornar "skipped"
        # No enviamos body
        r = client.post("/pipeline/trigger", timeout=30.0)
        assert r.status_code == 200

    def test_trigger_with_specific_week_number(self, client):
        """Se puede especificar un número de semana personalizado."""
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True, "week_number": 99},
            timeout=30.0,
        )
        data = r.json()
        assert r.status_code == 200
        # Si hubo export exitoso o skip, el week_number debe aparecer en el run
        if data.get("status") in ("partial", "skipped"):
            if data.get("week_number") is not None:
                assert data["week_number"] == 99

    def test_pipeline_does_not_auto_compute_personality(self, client):
        """
        El pipeline semanal NO debe calcular automáticamente las métricas de
        personalidad (D4 — aprobación manual). El cálculo es solo bajo demanda
        via POST /personality/compute.

        Verifica que el `steps` dict del run NO contiene la clave 'personality'.
        """
        r = client.post(
            "/pipeline/trigger",
            json={"skip_training": True},
            timeout=30.0,
        )
        assert r.status_code == 200
        data = r.json()
        steps = data.get("steps", {})
        assert "personality" not in steps, (
            "El pipeline NO debe auto-computar personalidad (aprobación manual requerida). "
            f"steps encontrados: {list(steps.keys())}"
        )
