"""
Pipeline Manager — Orquesta el ciclo semanal de aprendizaje episódico (Capa 2).

Flujo (cada domingo 23:00):
  1. Export   → extrae interacciones quality>=0.6 de los últimos 7 días → .jsonl
  2. Validate → verifica estructura ChatML y mínimo 50 ejemplos
  3. Train    → entrena LoRA Capa 2 con Unsloth (subproceso, ~15-30 min)
  4. Deploy   → fusiona Capa1 + Capa2 → casiopy:weekN (subproceso)
  5. Test     → anti-lobotomy vía ollama (subproceso)
  6. Si falla el test: revierte al modelo anterior (el deploy ya está en Ollama,
     simplemente se mantiene el modelo anterior como activo)

Estado persistido en pipeline_state.json (raíz del servicio).
"""

import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from interaction_manager import InteractionManager

# ─── Rutas ────────────────────────────────────────────────────────────────────
_SRC_DIR     = Path(__file__).parent
_SERVICE_DIR = _SRC_DIR.parent
SCRIPTS_DIR  = _SERVICE_DIR / "scripts"
EXPORTS_DIR  = _SERVICE_DIR / "exports" / "episodic"
STATE_FILE   = _SERVICE_DIR / "pipeline_state.json"

# ─── Parámetros ───────────────────────────────────────────────────────────────
MIN_EXAMPLES   = 50
QUALITY_THRESH = 0.6
EXPORT_DAYS    = 7

# ─── Lock global — evita runs concurrentes ───────────────────────────────────
_pipeline_lock = asyncio.Lock()


# ═══════════════════════════════════════════════════════════════════════════════
# Estado persistido en JSON
# ═══════════════════════════════════════════════════════════════════════════════

def _default_state() -> Dict[str, Any]:
    return {
        "current_model":  "casiopy:v1",
        "previous_model": None,
        "next_run":       None,
        "last_run":       None,
        "run_history":    [],
    }


def load_state() -> Dict[str, Any]:
    """Lee pipeline_state.json; devuelve estado por defecto si no existe o está corrupto."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"[pipeline] estado corrupto, usando default: {exc}")
    return _default_state()


def save_state(state: Dict[str, Any]) -> None:
    """Persiste el estado en pipeline_state.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, default=str), encoding="utf-8"
    )


def _update_next_run(state: Dict[str, Any]) -> None:
    """Calcula y guarda la próxima ejecución (domingo siguiente a las 23:00)."""
    now = datetime.now()
    days_ahead = (6 - now.weekday()) % 7   # 6 = domingo
    if days_ahead == 0 and now.hour >= 23:
        days_ahead = 7
    next_sunday = (now + timedelta(days=days_ahead)).replace(
        hour=23, minute=0, second=0, microsecond=0
    )
    state["next_run"] = next_sunday.isoformat()


def _finish_run(state: Dict[str, Any], run: Dict[str, Any]) -> None:
    """Marca el run como terminado, actualiza el estado y lo persiste."""
    run["finished_at"] = datetime.now().isoformat()
    state["last_run"] = run
    state.setdefault("run_history", []).append(run)
    state["run_history"] = state["run_history"][-20:]   # mantener solo 20
    _update_next_run(state)
    save_state(state)
    logger.info(f"[pipeline] run finalizado — status={run['status']}")


# ═══════════════════════════════════════════════════════════════════════════════
# Pasos del pipeline
# ═══════════════════════════════════════════════════════════════════════════════

async def _step_export(db: AsyncSession, week_number: int) -> Dict[str, Any]:
    """Exporta interacciones de los últimos 7 días en formato ChatML (user+assistant)."""
    logger.info(f"[pipeline] export — semana {week_number}")
    mgr = InteractionManager(db)
    rows = await mgr.get_training_ready_interactions(
        min_quality=QUALITY_THRESH,
        limit=10_000,
        days=EXPORT_DAYS,
    )

    if not rows:
        return {"status": "skipped", "examples": 0, "reason": "sin datos elegibles"}

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = EXPORTS_DIR / f"episodic_week_{week_number:03d}_{ts}.jsonl"

    # Export ponderado: oversampling según quality_score
    # quality < 0.75  → 1x | 0.75–0.89 → 1x | 0.90–1.00 → 2x
    entries: List[Dict[str, Any]] = []
    for row in rows:
        qs = row.get("quality_score") or QUALITY_THRESH
        repeat = max(1, round(qs / QUALITY_THRESH))
        entry = {
            "messages": [
                {"role": "user",      "content": row["input_text"]},
                {"role": "assistant", "content": row["output_text"]},
            ],
            "metadata": {
                "interaction_id": row["id"],
                "quality_score":  qs,
                "timestamp":      str(row.get("timestamp", "")),
                "repeat":         repeat,
            },
        }
        entries.extend([entry] * repeat)

    # Mezclar para evitar sesgo de orden durante el entrenamiento
    random.shuffle(entries)

    with file_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    unique_source = len(rows)
    total_written = len(entries)
    logger.info(
        f"[pipeline] exportados {total_written} ejemplos "
        f"({unique_source} únicos, oversampling aplicado) → {file_path}"
    )
    return {
        "status":        "success",
        "examples":      total_written,
        "unique_source": unique_source,
        "file_path":     str(file_path),
    }


def _step_validate(file_path: str) -> Dict[str, Any]:
    """Valida el JSONL exportado (estructura + mínimo de ejemplos)."""
    logger.info(f"[pipeline] validate — {file_path}")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validate_dataset", SCRIPTS_DIR / "validate_dataset.py"
    )
    mod = importlib.util.module_from_spec(spec)   # type: ignore
    spec.loader.exec_module(mod)                  # type: ignore
    return mod.validate_dataset_flexible(file_path, min_count=MIN_EXAMPLES)


async def _step_subprocess(
    args: List[str], step_name: str, timeout: int = 3600
) -> Dict[str, Any]:
    """Ejecuta un script pesado como subproceso y captura su salida."""
    logger.info(f"[pipeline] {step_name} → {' '.join(str(a) for a in args)}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRIPTS_DIR),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        rc = proc.returncode
        output = (
            stdout.decode("utf-8", errors="replace")
            + stderr.decode("utf-8", errors="replace")
        )
        if rc == 0:
            return {"status": "success", "output": output[-3000:]}
        else:
            return {"status": "failed", "rc": rc, "output": output[-3000:]}
    except asyncio.TimeoutError:
        return {"status": "failed", "reason": "timeout"}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


# ═══════════════════════════════════════════════════════════════════════════════
# Orquestador principal
# ═══════════════════════════════════════════════════════════════════════════════

async def run_pipeline(
    db: AsyncSession,
    week_number: Optional[int] = None,
    skip_training: bool = False,
) -> Dict[str, Any]:
    """
    Orquesta el pipeline completo de aprendizaje episódico.

    Args:
        db: Sesión de BD (para el paso de exportación).
        week_number: Número de semana ISO (por defecto, la semana actual).
        skip_training: Si True, salta train+deploy+test (útil para pruebas y CI).

    Returns:
        Resumen del run con status de cada paso.
        Posibles valores de status:
          "skipped"  — sin datos suficientes
          "partial"  — export+validate OK pero training saltado
          "failed"   — algún paso crítico falló
          "success"  — pipeline completo OK
          "already_running" — había otro run activo
    """
    if _pipeline_lock.locked():
        logger.warning("[pipeline] ya hay un run en curso, ignorando solicitud")
        return {"status": "already_running", "steps": {}, "error": None}

    async with _pipeline_lock:
        if week_number is None:
            week_number = datetime.now().isocalendar()[1]

        state = load_state()
        run: Dict[str, Any] = {
            "started_at":  datetime.now().isoformat(),
            "finished_at": None,
            "week_number": week_number,
            "status":      "running",
            "steps":       {},
            "error":       None,
        }
        logger.info(f"[pipeline] ══ inicio run semana {week_number} ══")

        # ── 1. Export ──────────────────────────────────────────────────────────
        try:
            export_result = await _step_export(db, week_number)
            run["steps"]["export"] = export_result
        except Exception as exc:
            run["steps"]["export"] = {"status": "failed", "reason": str(exc)}
            run["status"] = "failed"
            run["error"]  = f"export: {exc}"
            _finish_run(state, run)
            return run

        if export_result.get("examples", 0) == 0 or export_result["status"] == "skipped":
            run["status"] = "skipped"
            run["error"]  = export_result.get("reason", "sin datos de entrenamiento")
            _finish_run(state, run)
            return run

        # ── 2. Validate ────────────────────────────────────────────────────────
        try:
            val_result = _step_validate(export_result["file_path"])
            run["steps"]["validate"] = val_result
        except Exception as exc:
            run["steps"]["validate"] = {"status": "failed", "reason": str(exc)}
            run["status"] = "failed"
            run["error"]  = f"validate: {exc}"
            _finish_run(state, run)
            return run

        if val_result.get("status") != "success":
            run["status"] = "skipped"
            run["error"]  = val_result.get("reason", "dataset inválido")
            _finish_run(state, run)
            return run

        # skip_training: terminamos aquí con éxito parcial (export+validate OK)
        if skip_training:
            run["status"] = "partial"
            run["error"]  = "training saltado (skip_training=True)"
            _finish_run(state, run)
            return run

        # ── 3. Train ───────────────────────────────────────────────────────────
        train_result = await _step_subprocess(
            [
                sys.executable,
                str(SCRIPTS_DIR / "train_episodic_lora.py"),
                "--dataset", export_result["file_path"],
                "--week",    str(week_number),
            ],
            step_name="train",
        )
        run["steps"]["train"] = train_result
        if train_result["status"] != "success":
            run["status"] = "failed"
            run["error"]  = "entrenamiento falló"
            _finish_run(state, run)
            return run

        # ── 4. Deploy → casiopy:weekN ──────────────────────────────────────────
        candidate_model = f"casiopy:week{week_number:02d}"
        deploy_result = await _step_subprocess(
            [
                sys.executable,
                str(SCRIPTS_DIR / "deploy_to_ollama.py"),
                "--week", str(week_number),
            ],
            step_name="deploy",
        )
        run["steps"]["deploy"] = deploy_result
        if deploy_result["status"] != "success":
            run["status"] = "failed"
            run["error"]  = "deploy falló"
            _finish_run(state, run)
            return run

        # ── 5. Test anti-lobotomy ──────────────────────────────────────────────
        test_result = await _step_subprocess(
            [
                sys.executable,
                str(SCRIPTS_DIR / "test_personality.py"),
                "--model", candidate_model,
                "--save-report",
            ],
            step_name="personality_test",
            timeout=300,  # 5 min máx para las 8 preguntas via ollama
        )
        run["steps"]["test"] = test_result

        if test_result["status"] != "success":
            logger.warning(
                f"[pipeline] anti-lobotomy falló para {candidate_model}. "
                f"Revertiendo: {state['current_model']} sigue activo."
            )
            run["status"] = "failed"
            run["error"]  = "anti-lobotomy falló — modelo anterior sigue activo"
            _finish_run(state, run)
            return run

        # ── Éxito total ────────────────────────────────────────────────────────
        state["previous_model"] = state.get("current_model")
        state["current_model"]  = candidate_model
        run["status"] = "success"
        logger.info(f"[pipeline] ✅ completado — modelo activo: {candidate_model}")

        _finish_run(state, run)
        return run
