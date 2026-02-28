"""
Interaction Manager - Gestión de interacciones y conversaciones
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import uuid


class InteractionManager:
    """
    Gestor de interacciones (input/output) para capturar conversaciones
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_session(
        self, user_id: Optional[str] = None, opt_out_training: bool = False
    ) -> str:
        """
        Crear nueva sesión de conversación

        Args:
            user_id: ID del usuario (opcional)
            opt_out_training: Si el usuario NO quiere que se use para entrenamiento

        Returns:
            UUID de la sesión creada
        """
        session_id = str(uuid.uuid4())

        query = """
        INSERT INTO sessions (id, user_id, started_at, opt_out_training)
        VALUES (:session_id, :user_id, NOW(), :opt_out_training)
        RETURNING id
        """

        result = await self.db.execute(
            query,
            {
                "session_id": session_id,
                "user_id": user_id,
                "opt_out_training": opt_out_training,
            },
        )

        logger.info(f"✅ Nueva sesión creada: {session_id}")
        return session_id

    async def end_session(self, session_id: str) -> bool:
        """
        Finalizar sesión y calcular estadísticas

        Args:
            session_id: UUID de la sesión

        Returns:
            True si se finalizó correctamente
        """
        # Calcular estadísticas de la sesión
        stats_query = """
        UPDATE sessions
        SET
            ended_at = NOW(),
            total_turns = (SELECT COUNT(*) FROM interactions WHERE session_id = :session_id),
            avg_quality_score = (SELECT AVG(quality_score) FROM interactions WHERE session_id = :session_id)
        WHERE id = :session_id
        """

        await self.db.execute(stats_query, {"session_id": session_id})
        logger.info(f"✅ Sesión finalizada: {session_id}")
        return True

    async def store_interaction(
        self,
        session_id: str,
        input_text: str,
        output_text: str,
        input_emotion: Optional[str] = None,
        output_emotion: Optional[str] = None,
        input_method: str = "text",
        user_id: Optional[str] = None,
        conversation_turn: int = 0,
        previous_topic: Optional[str] = None,
        latency_ms: Optional[int] = None,
        model_version: Optional[str] = None,
        output_confidence: Optional[float] = None,
        input_embedding: Optional[List[float]] = None,
        output_embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Almacenar una interacción (input/output)

        Args:
            session_id: UUID de la sesión
            input_text: Texto del usuario
            output_text: Respuesta de Casiopy
            input_emotion: Emoción detectada en el input
            output_emotion: Emoción con la que se respondió
            input_method: 'text' o 'voice'
            user_id: ID del usuario
            conversation_turn: Número de turno en la conversación
            previous_topic: Tema del contexto anterior
            latency_ms: Latencia de respuesta
            model_version: Versión del modelo usado
            output_confidence: Confianza de la respuesta
            input_embedding: Vector embedding del input
            output_embedding: Vector embedding del output

        Returns:
            UUID de la interacción creada
        """
        interaction_id = str(uuid.uuid4())

        # Convertir embeddings a formato pgvector si existen
        input_emb_str = None
        if input_embedding:
            input_emb_str = "[" + ",".join(map(str, input_embedding)) + "]"

        output_emb_str = None
        if output_embedding:
            output_emb_str = "[" + ",".join(map(str, output_embedding)) + "]"

        query = """
        INSERT INTO interactions (
            id, session_id, user_id, timestamp,
            input_text, input_method, input_emotion,
            output_text, output_emotion, output_confidence,
            conversation_turn, previous_topic,
            latency_ms, model_version,
            input_embedding, output_embedding
        ) VALUES (
            :interaction_id, :session_id, :user_id, NOW(),
            :input_text, :input_method, :input_emotion,
            :output_text, :output_emotion, :output_confidence,
            :conversation_turn, :previous_topic,
            :latency_ms, :model_version,
            :input_embedding, :output_embedding
        )
        RETURNING id
        """

        try:
            await self.db.execute(
                query,
                {
                    "interaction_id": interaction_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "input_text": input_text,
                    "input_method": input_method,
                    "input_emotion": input_emotion,
                    "output_text": output_text,
                    "output_emotion": output_emotion,
                    "output_confidence": output_confidence,
                    "conversation_turn": conversation_turn,
                    "previous_topic": previous_topic,
                    "latency_ms": latency_ms,
                    "model_version": model_version,
                    "input_embedding": input_emb_str,
                    "output_embedding": output_emb_str,
                },
            )

            logger.debug(f"💾 Interacción almacenada: {interaction_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"❌ Error al almacenar interacción: {e}")
            raise

    async def get_session_interactions(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todas las interacciones de una sesión

        Args:
            session_id: UUID de la sesión
            limit: Límite de interacciones a devolver

        Returns:
            Lista de interacciones
        """
        query = """
        SELECT
            id, session_id, user_id, timestamp,
            input_text, input_emotion, input_method,
            output_text, output_emotion, output_confidence,
            conversation_turn, previous_topic,
            latency_ms, model_version, quality_score, is_training_ready
        FROM interactions
        WHERE session_id = :session_id
        ORDER BY timestamp ASC
        LIMIT :limit
        """

        result = await self.db.execute(query, {"session_id": session_id, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": row[2],
                "timestamp": row[3],
                "input_text": row[4],
                "input_emotion": row[5],
                "input_method": row[6],
                "output_text": row[7],
                "output_emotion": row[8],
                "output_confidence": row[9],
                "conversation_turn": row[10],
                "previous_topic": row[11],
                "latency_ms": row[12],
                "model_version": row[13],
                "quality_score": row[14],
                "is_training_ready": row[15],
            }
            for row in rows
        ]

    async def get_recent_interactions(
        self, days: int = 7, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Obtener interacciones recientes

        Args:
            days: Número de días hacia atrás
            limit: Límite de interacciones

        Returns:
            Lista de interacciones
        """
        query = """
        SELECT
            id, session_id, user_id, timestamp,
            input_text, input_emotion,
            output_text, output_emotion,
            quality_score, is_training_ready
        FROM interactions
        WHERE timestamp >= NOW() - INTERVAL ':days days'
        ORDER BY timestamp DESC
        LIMIT :limit
        """

        result = await self.db.execute(query, {"days": days, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": row[2],
                "timestamp": row[3],
                "input_text": row[4],
                "input_emotion": row[5],
                "output_text": row[6],
                "output_emotion": row[7],
                "quality_score": row[8],
                "is_training_ready": row[9],
            }
            for row in rows
        ]

    async def mark_training_ready(
        self, interaction_id: str, quality_score: float
    ) -> bool:
        """
        Marcar interacción como lista para entrenamiento

        Args:
            interaction_id: UUID de la interacción
            quality_score: Puntuación de calidad (0-1)

        Returns:
            True si se marcó correctamente
        """
        query = """
        UPDATE interactions
        SET
            quality_score = :quality_score,
            is_training_ready = CASE
                WHEN :quality_score >= 0.6 THEN true
                ELSE false
            END
        WHERE id = :interaction_id
        """

        await self.db.execute(
            query, {"interaction_id": interaction_id, "quality_score": quality_score}
        )

        logger.debug(
            f"✅ Interacción marcada (quality={quality_score}): {interaction_id}"
        )
        return True

    async def get_training_ready_interactions(
        self, min_quality: float = 0.6, limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Obtener interacciones listas para entrenamiento

        Args:
            min_quality: Puntuación mínima de calidad
            limit: Límite de interacciones

        Returns:
            Lista de interacciones listas para exportar
        """
        query = """
        SELECT
            i.id, i.session_id, i.timestamp,
            i.input_text, i.input_emotion,
            i.output_text, i.output_emotion,
            i.quality_score, i.conversation_turn,
            s.user_id, s.opt_out_training
        FROM interactions i
        JOIN sessions s ON i.session_id = s.id
        WHERE i.is_training_ready = true
          AND i.quality_score >= :min_quality
          AND s.opt_out_training = false
          AND i.training_export_id IS NULL
        ORDER BY i.timestamp DESC
        LIMIT :limit
        """

        result = await self.db.execute(
            query, {"min_quality": min_quality, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "session_id": str(row[1]),
                "timestamp": row[2],
                "input_text": row[3],
                "input_emotion": row[4],
                "output_text": row[5],
                "output_emotion": row[6],
                "quality_score": row[7],
                "conversation_turn": row[8],
                "user_id": row[9],
                "opt_out_training": row[10],
            }
            for row in rows
        ]

    async def add_feedback(
        self,
        interaction_id: str,
        feedback_type: str,
        user_reaction: Optional[str] = None,
        corrected_response: Optional[str] = None,
    ) -> str:
        """
        Agregar feedback del usuario a una interacción

        Args:
            interaction_id: UUID de la interacción
            feedback_type: 'positive', 'negative', 'correction'
            user_reaction: 'liked', 'disliked', 'neutral'
            corrected_response: Respuesta corregida si aplica

        Returns:
            UUID del feedback creado
        """
        feedback_id = str(uuid.uuid4())

        query = """
        INSERT INTO feedback (
            id, interaction_id, feedback_type, user_reaction, corrected_response, timestamp
        ) VALUES (
            :feedback_id, :interaction_id, :feedback_type, :user_reaction, :corrected_response, NOW()
        )
        RETURNING id
        """

        await self.db.execute(
            query,
            {
                "feedback_id": feedback_id,
                "interaction_id": interaction_id,
                "feedback_type": feedback_type,
                "user_reaction": user_reaction,
                "corrected_response": corrected_response,
            },
        )

        logger.info(f"📝 Feedback registrado: {feedback_type} para {interaction_id}")
        return feedback_id

    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas generales de interacciones

        Returns:
            Diccionario con estadísticas
        """
        query = """
        SELECT
            COUNT(*) as total_interactions,
            COUNT(DISTINCT session_id) as total_sessions,
            COUNT(CASE WHEN is_training_ready THEN 1 END) as training_ready,
            AVG(quality_score) as avg_quality,
            AVG(latency_ms) as avg_latency_ms,
            MIN(timestamp) as first_interaction,
            MAX(timestamp) as last_interaction
        FROM interactions
        """

        result = await self.db.execute(query)
        row = result.fetchone()

        # Stats de últimos 7 días
        recent_query = """
        SELECT COUNT(*) as count_7d
        FROM interactions
        WHERE timestamp >= NOW() - INTERVAL '7 days'
        """
        recent_result = await self.db.execute(recent_query)
        recent_row = recent_result.fetchone()

        return {
            "total_interactions": row[0],
            "total_sessions": row[1],
            "training_ready_count": row[2],
            "avg_quality_score": float(row[3]) if row[3] else None,
            "avg_latency_ms": float(row[4]) if row[4] else None,
            "first_interaction": row[5],
            "last_interaction": row[6],
            "interactions_last_7_days": recent_row[0],
        }
