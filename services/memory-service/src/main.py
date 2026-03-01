"""
Casiopy Memory Service - FastAPI Application
"""

import asyncio
import os
from fastapi import FastAPI, Depends, HTTPException, status, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from loguru import logger
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from database import get_db, init_db, close_db, AsyncSessionLocal
from core_memory import CoreMemoryManager
from interaction_manager import InteractionManager
from pipeline_manager import load_state, run_pipeline
from scheduler import start_scheduler, stop_scheduler, get_next_run_time
from embedding_service import embedding_service
from personality_analyzer import PersonalityAnalyzer

# Cargar variables de entorno
load_dotenv()

# Configuración
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8006"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configurar logger
logger.add(
    "./logs/memory_service.log",
    rotation="500 MB",
    retention="30 days",
    level=LOG_LEVEL,
)

# Crear aplicación FastAPI
app = FastAPI(
    title="Casiopy Memory Service",
    description="Sistema de memoria persistente y evolutiva para Casiopy VTuber AI",
    version="1.0.1",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODELOS PYDANTIC
# ============================================================


class CoreMemoryEntry(BaseModel):
    category: str = Field(..., description="Categoría de memoria")
    key: str = Field(..., description="Clave única")
    value: str = Field(..., description="Valor/contenido")
    is_mutable: bool = Field(False, description="Si se puede modificar")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CoreMemoryUpdate(BaseModel):
    new_value: str = Field(..., description="Nuevo valor")


class SessionCreate(BaseModel):
    user_id: Optional[str] = None
    opt_out_training: bool = False


class InteractionCreate(BaseModel):
    session_id: str
    input_text: str
    output_text: str
    input_emotion: Optional[str] = None
    output_emotion: Optional[str] = None
    input_method: str = "text"
    user_id: Optional[str] = None
    conversation_turn: int = 0
    previous_topic: Optional[str] = None
    latency_ms: Optional[int] = None
    model_version: Optional[str] = None
    output_confidence: Optional[float] = None


class FeedbackCreate(BaseModel):
    interaction_id: str
    feedback_type: str = Field(..., pattern="^(positive|negative|correction)$")
    user_reaction: Optional[str] = Field(None, pattern="^(liked|disliked|neutral)$")
    corrected_response: Optional[str] = None


class QualityScoreUpdate(BaseModel):
    quality_score: float = Field(..., ge=0.0, le=1.0)


class SemanticResult(BaseModel):
    interaction_id: str
    input_text: str
    output_text: str
    similarity: float
    timestamp: Any
    input_emotion: Optional[str]
    output_emotion: Optional[str]


class SemanticSearchResponse(BaseModel):
    query: str
    threshold: float
    results: List[SemanticResult]
    count: int


# ============================================================
# HELPERS INTERNOS
# ============================================================


async def _embed_and_update(
    interaction_id: str, input_text: str, output_text: str
) -> None:
    """Genera embeddings y los persiste en background (sin bloquear la respuesta HTTP)."""
    try:
        in_vec  = embedding_service.encode(input_text)
        out_vec = embedding_service.encode(output_text)
        in_str  = "[" + ",".join(map(str, in_vec))  + "]"
        out_str = "[" + ",".join(map(str, out_vec)) + "]"
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    UPDATE interactions
                    SET input_embedding  = CAST(:in_emb  AS vector),
                        output_embedding = CAST(:out_emb AS vector)
                    WHERE id = :iid
                """),
                {"in_emb": in_str, "out_emb": out_str, "iid": interaction_id},
            )
            await db.commit()
        logger.debug(f"[embed] embeddings guardados para {interaction_id}")
    except Exception as exc:
        logger.warning(f"[embed] fallo embeddings {interaction_id}: {exc}")


# ============================================================
# EVENTOS DE APLICACIÓN
# ============================================================


@app.on_event("startup")
async def startup_event():
    """Inicializar conexión a base de datos y scheduler al arrancar."""
    logger.info("🚀 Iniciando Casiopy Memory Service...")
    success = await init_db()
    if success:
        logger.info("✅ Base de datos iniciada correctamente")
    else:
        logger.error("❌ Error al conectar con la base de datos")
    start_scheduler()
    logger.info("✅ Servicio iniciado correctamente")


@app.on_event("shutdown")
async def shutdown_event():
    """Cerrar scheduler y conexiones al apagar."""
    logger.info("🔌 Cerrando Casiopy Memory Service...")
    stop_scheduler()
    await close_db()
    logger.info("✅ Servicio cerrado correctamente")


# ============================================================
# ENDPOINTS - HEALTH CHECK
# ============================================================


@app.get("/", tags=["Health"])
async def root():
    """Health check básico"""
    return {
        "service": "Casiopy Memory Service",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check detallado con verificación de DB"""
    try:
        # Verificar conexión a DB
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "service": "memory-service",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )


# ============================================================
# ENDPOINTS - CORE MEMORY (Capa 0)
# ============================================================


@app.get("/core-memory", tags=["Core Memory"])
async def get_all_core_memory(db: AsyncSession = Depends(get_db)):
    """Obtener toda la core memory"""
    manager = CoreMemoryManager(db)
    return await manager.get_all()


# IMPORTANTE: rutas fijas ANTES de las parametrizadas para evitar conflictos de matching
@app.get("/core-memory/system-prompt/generate", tags=["Core Memory"])
async def generate_system_prompt(db: AsyncSession = Depends(get_db)):
    """Generar system prompt completo a partir de core memory"""
    manager = CoreMemoryManager(db)
    prompt = await manager.generate_system_prompt()
    return {"system_prompt": prompt}


@app.get("/core-memory/stats", tags=["Core Memory"])
async def get_core_memory_stats(db: AsyncSession = Depends(get_db)):
    """Obtener estadísticas de core memory"""
    manager = CoreMemoryManager(db)
    return await manager.get_stats()


@app.get("/core-memory/{category}", tags=["Core Memory"])
async def get_core_memory_by_category(category: str, db: AsyncSession = Depends(get_db)):
    """Obtener core memory por categoría"""
    manager = CoreMemoryManager(db)
    return await manager.get_by_category(category)


@app.get("/core-memory/{category}/{key}", tags=["Core Memory"])
async def get_core_memory_entry(
    category: str, key: str, db: AsyncSession = Depends(get_db)
):
    """Obtener una entrada específica de core memory"""
    manager = CoreMemoryManager(db)
    entry = await manager.get_by_key(category, key)
    if not entry:
        raise HTTPException(status_code=404, detail="Core memory entry not found")
    return entry


@app.post("/core-memory", tags=["Core Memory"], status_code=status.HTTP_201_CREATED)
async def add_core_memory_entry(
    entry: CoreMemoryEntry, db: AsyncSession = Depends(get_db)
):
    """Agregar nueva entrada a core memory"""
    manager = CoreMemoryManager(db)
    try:
        return await manager.add_entry(
            category=entry.category,
            key=entry.key,
            value=entry.value,
            is_mutable=entry.is_mutable,
            metadata=entry.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/core-memory/{category}/{key}", tags=["Core Memory"])
async def update_core_memory_entry(
    category: str, key: str, update: CoreMemoryUpdate, db: AsyncSession = Depends(get_db)
):
    """Actualizar entrada de core memory (solo si is_mutable=true)"""
    manager = CoreMemoryManager(db)
    result = await manager.update_entry(category, key, update.new_value)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Cannot update: entry not found or is immutable",
        )
    return result


@app.delete("/core-memory/{category}/{key}", tags=["Core Memory"])
async def delete_core_memory_entry(
    category: str, key: str, db: AsyncSession = Depends(get_db)
):
    """Eliminar entrada de core memory (solo si is_mutable=true)"""
    manager = CoreMemoryManager(db)
    success = await manager.delete_entry(category, key)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete: entry not found or is immutable",
        )
    return {"status": "deleted", "category": category, "key": key}


# ============================================================
# ENDPOINTS - SESSIONS & INTERACTIONS
# ============================================================


@app.post("/sessions", tags=["Sessions"], status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate, db: AsyncSession = Depends(get_db)
):
    """Crear nueva sesión de conversación"""
    manager = InteractionManager(db)
    session_id = await manager.create_session(
        user_id=session_data.user_id,
        opt_out_training=session_data.opt_out_training,
    )
    return {"session_id": session_id}


@app.post("/sessions/{session_id}/end", tags=["Sessions"])
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Finalizar sesión y calcular estadísticas"""
    manager = InteractionManager(db)
    success = await manager.end_session(session_id)
    return {"status": "ended", "session_id": session_id}


@app.post("/interactions", tags=["Interactions"], status_code=status.HTTP_201_CREATED)
async def store_interaction(
    interaction: InteractionCreate, db: AsyncSession = Depends(get_db)
):
    """Almacenar una interacción (input/output)"""
    manager = InteractionManager(db)
    interaction_id = await manager.store_interaction(
        session_id=interaction.session_id,
        input_text=interaction.input_text,
        output_text=interaction.output_text,
        input_emotion=interaction.input_emotion,
        output_emotion=interaction.output_emotion,
        input_method=interaction.input_method,
        user_id=interaction.user_id,
        conversation_turn=interaction.conversation_turn,
        previous_topic=interaction.previous_topic,
        latency_ms=interaction.latency_ms,
        model_version=interaction.model_version,
        output_confidence=interaction.output_confidence,
    )
    # Generar embeddings en background sin bloquear la respuesta
    asyncio.create_task(
        _embed_and_update(interaction_id, interaction.input_text, interaction.output_text)
    )
    return {"interaction_id": interaction_id}


@app.get("/sessions/{session_id}/interactions", tags=["Interactions"])
async def get_session_interactions(
    session_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Obtener todas las interacciones de una sesión"""
    manager = InteractionManager(db)
    interactions = await manager.get_session_interactions(session_id, limit)
    return {"session_id": session_id, "interactions": interactions}


@app.get("/interactions/recent", tags=["Interactions"])
async def get_recent_interactions(
    days: int = 7, limit: int = 1000, db: AsyncSession = Depends(get_db)
):
    """Obtener interacciones recientes"""
    manager = InteractionManager(db)
    interactions = await manager.get_recent_interactions(days, limit)
    return {"days": days, "count": len(interactions), "interactions": interactions}


@app.get("/interactions/training-ready", tags=["Interactions"])
async def get_training_ready_interactions(
    min_quality: float = 0.6, limit: int = 10000, db: AsyncSession = Depends(get_db)
):
    """Obtener interacciones listas para entrenamiento"""
    manager = InteractionManager(db)
    interactions = await manager.get_training_ready_interactions(min_quality, limit)
    return {
        "min_quality": min_quality,
        "count": len(interactions),
        "interactions": interactions,
    }


@app.delete("/interactions/{interaction_id}", tags=["Interactions"])
async def delete_interaction(
    interaction_id: str, db: AsyncSession = Depends(get_db)
):
    """Eliminar una interacción y su feedback asociado (borrado definitivo)."""
    # Eliminar feedback antes que la interacción (FK constraint)
    await db.execute(
        text("DELETE FROM feedback WHERE interaction_id = :id"),
        {"id": interaction_id},
    )
    result = await db.execute(
        text("DELETE FROM interactions WHERE id = :id RETURNING id"),
        {"id": interaction_id},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Interaction not found")
    await db.commit()
    return {"status": "deleted", "interaction_id": interaction_id}


@app.put("/interactions/{interaction_id}/quality", tags=["Interactions"])
async def update_interaction_quality(
    interaction_id: str, quality: QualityScoreUpdate, db: AsyncSession = Depends(get_db)
):
    """Actualizar quality score de una interacción"""
    manager = InteractionManager(db)
    success = await manager.mark_training_ready(interaction_id, quality.quality_score)
    return {
        "interaction_id": interaction_id,
        "quality_score": quality.quality_score,
        "training_ready": quality.quality_score >= 0.6,
    }


@app.post("/feedback", tags=["Feedback"], status_code=status.HTTP_201_CREATED)
async def add_feedback(feedback: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    """Agregar feedback del usuario a una interacción"""
    manager = InteractionManager(db)
    feedback_id = await manager.add_feedback(
        interaction_id=feedback.interaction_id,
        feedback_type=feedback.feedback_type,
        user_reaction=feedback.user_reaction,
        corrected_response=feedback.corrected_response,
    )
    return {"feedback_id": feedback_id}


@app.get("/stats", tags=["Stats"])
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Obtener estadísticas generales del servicio"""
    core_manager = CoreMemoryManager(db)
    interaction_manager = InteractionManager(db)

    core_stats = await core_manager.get_stats()
    interaction_stats = await interaction_manager.get_stats()

    return {
        "core_memory": core_stats,
        "interactions": interaction_stats,
    }


# ============================================================
# ENDPOINTS - PIPELINE DE ENTRENAMIENTO EPISÓDICO
# ============================================================


class PipelineTriggerRequest(BaseModel):
    skip_training: bool = Field(
        False,
        description="Si True, ejecuta solo export+validate sin entrenar (útil para CI/tests).",
    )
    week_number: Optional[int] = Field(
        None, description="Número de semana ISO. Por defecto la semana actual."
    )


@app.get("/pipeline/status", tags=["Pipeline"])
async def pipeline_status():
    """
    Estado actual del pipeline: modelo activo, próxima ejecución y último run.
    No requiere conexión a BD — lee pipeline_state.json.
    """
    state = load_state()
    next_run = get_next_run_time() or state.get("next_run")
    return {
        "current_model":  state.get("current_model"),
        "previous_model": state.get("previous_model"),
        "next_run":       next_run,
        "last_run":       state.get("last_run"),
    }


@app.get("/pipeline/history", tags=["Pipeline"])
async def pipeline_history():
    """
    Historial de los últimos 20 runs del pipeline.
    No requiere conexión a BD — lee pipeline_state.json.
    """
    state = load_state()
    return {
        "count":   len(state.get("run_history", [])),
        "history": state.get("run_history", []),
    }


@app.post("/pipeline/trigger", tags=["Pipeline"])
async def pipeline_trigger(
    body: PipelineTriggerRequest = Body(default=PipelineTriggerRequest()),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispara el pipeline manualmente.

    Con skip_training=True el pipeline ejecuta solo export+validate y termina
    con status "partial" (o "skipped" si no hay datos). Útil para pruebas.

    Nota: El endpoint es síncrono respecto al run — espera a que el pipeline
    termine antes de responder. Con skip_training=False y datos suficientes,
    el entrenamiento puede tardar 15-30 minutos.
    """
    result = await run_pipeline(
        db,
        week_number=body.week_number,
        skip_training=body.skip_training,
    )
    return result


# ============================================================
# ENDPOINTS - BÚSQUEDA SEMÁNTICA (Fase 3)
# ============================================================


@app.get("/embed", tags=["Semantic"])
async def embed_text(text_input: str = Query(..., alias="text")):
    """Devuelve el embedding (384 dims) de un texto arbitrario."""
    vec = embedding_service.encode(text_input)
    return {"text": text_input, "embedding": vec, "dimensions": len(vec)}


@app.get("/search", tags=["Semantic"], response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., description="Texto de búsqueda"),
    threshold: float = Query(0.75, ge=0.0, le=1.0, description="Similitud mínima (coseno)"),
    limit: int = Query(3, ge=1, le=20, description="Máximo de resultados"),
    days: int = Query(90, ge=1, description="Ventana temporal en días"),
    db: AsyncSession = Depends(get_db),
):
    """
    Busca interacciones pasadas semánticamente similares a la consulta.

    Usa pgvector con índice ivfflat (coseno). Solo devuelve resultados con
    similarity >= threshold. Retorna lista vacía si no hay embeddings aún.
    """
    query_vec = embedding_service.encode(q)
    qvec_str  = "[" + ",".join(map(str, query_vec)) + "]"
    max_dist  = 1.0 - threshold   # distancia coseno máxima aceptada

    result = await db.execute(
        text("""
            SELECT id,
                   input_text,
                   output_text,
                   1 - (input_embedding <=> CAST(:qvec AS vector)) AS similarity,
                   timestamp,
                   input_emotion,
                   output_emotion
            FROM interactions
            WHERE input_embedding IS NOT NULL
              AND timestamp >= NOW() - (:days * INTERVAL '1 day')
              AND (input_embedding <=> CAST(:qvec AS vector)) <= :max_dist
            ORDER BY input_embedding <=> CAST(:qvec AS vector) ASC
            LIMIT :limit
        """),
        {"qvec": qvec_str, "days": days, "max_dist": max_dist, "limit": limit},
    )
    rows = result.fetchall()

    results = [
        SemanticResult(
            interaction_id=str(r.id),
            input_text=r.input_text or "",
            output_text=r.output_text or "",
            similarity=float(r.similarity),
            timestamp=str(r.timestamp),
            input_emotion=r.input_emotion,
            output_emotion=r.output_emotion,
        )
        for r in rows
    ]

    return SemanticSearchResponse(
        query=q,
        threshold=threshold,
        results=results,
        count=len(results),
    )


# ============================================================
# ENDPOINTS - PERSONALIDAD (Fase 3.3)
# IMPORTANTE: rutas fijas ANTES de cualquier ruta /{id} parametrizada
# ============================================================


@app.get("/personality/metrics", tags=["Personality"])
async def get_personality_history(
    limit: int = Query(12, ge=1, le=52, description="Número de mediciones a devolver"),
    db: AsyncSession = Depends(get_db),
):
    """Historial de métricas de personalidad (más reciente primero)."""
    pa = PersonalityAnalyzer(db)
    history = await pa.get_history(limit=limit)
    return {"count": len(history), "metrics": history}


@app.get("/personality/metrics/latest", tags=["Personality"])
async def get_personality_latest(db: AsyncSession = Depends(get_db)):
    """Última medición de personalidad. 404 si aún no se ha calculado ninguna."""
    pa = PersonalityAnalyzer(db)
    latest = await pa.get_latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No hay métricas de personalidad aún")
    return latest


@app.post("/personality/compute", tags=["Personality"], status_code=status.HTTP_201_CREATED)
async def compute_personality(
    days: int = Query(7, ge=1, le=90, description="Ventana de análisis en días"),
    db: AsyncSession = Depends(get_db),
):
    """
    Calcula y persiste nuevas métricas de personalidad.

    Retorna 422 si hay menos de 10 interacciones en el período especificado.
    """
    pa = PersonalityAnalyzer(db)
    metrics = await pa.compute_metrics(days=days)
    if metrics is None:
        raise HTTPException(
            status_code=422,
            detail=f"Muestras insuficientes para calcular personalidad (mínimo {PersonalityAnalyzer.MIN_SAMPLE})",
        )
    inserted_id = await pa.store_metrics(metrics)
    await db.commit()
    return {"id": inserted_id, **metrics}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    logger.info(f"🚀 Iniciando servidor en {API_HOST}:{API_PORT}")
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=os.getenv("API_RELOAD", "true").lower() == "true",
    )
