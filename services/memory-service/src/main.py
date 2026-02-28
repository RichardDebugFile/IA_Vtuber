"""
Casiopy Memory Service - FastAPI Application
"""

import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from loguru import logger
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from database import get_db, init_db, close_db
from core_memory import CoreMemoryManager
from interaction_manager import InteractionManager

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
    version="1.0.0",
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


# ============================================================
# EVENTOS DE APLICACIÓN
# ============================================================


@app.on_event("startup")
async def startup_event():
    """Inicializar conexión a base de datos al arrancar"""
    logger.info("🚀 Iniciando Casiopy Memory Service...")
    success = await init_db()
    if success:
        logger.info("✅ Servicio iniciado correctamente")
    else:
        logger.error("❌ Error al iniciar el servicio")


@app.on_event("shutdown")
async def shutdown_event():
    """Cerrar conexiones al apagar"""
    logger.info("🔌 Cerrando Casiopy Memory Service...")
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
        await db.execute("SELECT 1")
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
