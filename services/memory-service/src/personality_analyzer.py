"""
PersonalityAnalyzer — Fase 3.3 (Personality Drifting Controlado).

Calcula métricas de personalidad ponderadas por quality_score a partir de las
interacciones recientes y las persiste en la tabla personality_metrics.

Uso típico (al final del pipeline semanal):
    async with AsyncSessionLocal() as db:
        pa = PersonalityAnalyzer(db)
        metrics = await pa.compute_metrics(days=7)
        if metrics:
            await pa.store_metrics(metrics)
            await db.commit()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Palabras clave que denotan profundidad técnica en la respuesta
_TECH_KEYWORDS = {
    "función", "función", "algoritmo", "código", "variable", "clase",
    "método", "bucle", "array", "lista", "diccionario", "objeto",
    "parámetro", "argumento", "retorna", "retorno", "import", "async",
    "await", "http", "api", "json", "base de datos", "query", "sql",
}

# Emociones que indican humor/diversión
_HUMOR_EMOTIONS = {"playful", "humor", "sarcastic", "amused", "witty"}

# Emociones que indican calidez/amabilidad
_FRIENDLY_EMOTIONS = {"warm", "empathetic", "friendly", "excited", "happy"}

# Emociones que indican sequedad/sarcasmo
_SARCASM_EMOTIONS = {"dry", "sarcastic", "cold", "flat", "deadpan"}


def _is_technical(text: str) -> float:
    """Devuelve 1.0 si el texto parece técnico, 0.0 si no."""
    if not text:
        return 0.0
    text_lower = text.lower()
    # Presencia de bloque de código
    if "```" in text_lower:
        return 1.0
    # Longitud media de palabras > 7 caracteres (indicador de vocabulario técnico)
    words = [w.strip(".,;:!?()[]{}\"'") for w in text_lower.split() if w.strip()]
    if words and (sum(len(w) for w in words) / len(words)) > 7:
        return 1.0
    # Palabras clave técnicas
    for kw in _TECH_KEYWORDS:
        if kw in text_lower:
            return 1.0
    return 0.0


class PersonalityAnalyzer:
    """Calcula y persiste métricas de personalidad de Casiopy."""

    MIN_SAMPLE = 10   # mínimo de interacciones para calcular métricas

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo de métricas
    # ──────────────────────────────────────────────────────────────────────────

    async def compute_metrics(self, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Calcula métricas de personalidad ponderadas por quality_score.

        Retorna None si hay < MIN_SAMPLE registros en el período.

        Métricas calculadas (cada una en [0.0, 1.0]):
          verbosity        — media de min(word_count/50, 1.0) ponderada
          humor_frequency  — proporción de respuestas con emoción humorística
          friendliness     — proporción de respuestas cálidas/amigables
          sarcasm_level    — proporción de respuestas secas/sarcásticas
          technical_depth  — proporción de respuestas técnicas
        """
        result = await self._db.execute(
            text("""
                SELECT output_text,
                       output_emotion,
                       COALESCE(quality_score, 0.5) AS weight
                FROM interactions
                WHERE timestamp >= NOW() - (:days * INTERVAL '1 day')
                  AND output_text IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 2000
            """),
            {"days": days},
        )
        rows = result.fetchall()

        if len(rows) < self.MIN_SAMPLE:
            logger.info(
                f"[personality] solo {len(rows)} muestras — mínimo {self.MIN_SAMPLE}"
            )
            return None

        total_weight = 0.0
        w_verbosity = 0.0
        w_humor = 0.0
        w_friendly = 0.0
        w_sarcasm = 0.0
        w_technical = 0.0

        for row in rows:
            output_text   = row.output_text or ""
            output_emotion = (row.output_emotion or "").lower()
            weight         = float(row.weight)

            # Verbosidad: longitud normalizada
            word_count = len(output_text.split())
            verbosity  = min(word_count / 50.0, 1.0)

            humor     = 1.0 if output_emotion in _HUMOR_EMOTIONS    else 0.0
            friendly  = 1.0 if output_emotion in _FRIENDLY_EMOTIONS else 0.0
            sarcasm   = 1.0 if output_emotion in _SARCASM_EMOTIONS  else 0.0
            technical = _is_technical(output_text)

            w_verbosity  += verbosity  * weight
            w_humor      += humor      * weight
            w_friendly   += friendly   * weight
            w_sarcasm    += sarcasm    * weight
            w_technical  += technical  * weight
            total_weight += weight

        if total_weight == 0:
            return None

        metrics: Dict[str, Any] = {
            "verbosity":        round(w_verbosity  / total_weight, 4),
            "humor_frequency":  round(w_humor      / total_weight, 4),
            "friendliness":     round(w_friendly   / total_weight, 4),
            "sarcasm_level":    round(w_sarcasm    / total_weight, 4),
            "technical_depth":  round(w_technical  / total_weight, 4),
            "sample_size":      len(rows),
            "days_analyzed":    days,
        }
        logger.info(f"[personality] métricas calculadas sobre {len(rows)} muestras: {metrics}")
        return metrics

    # ──────────────────────────────────────────────────────────────────────────
    # Persistencia
    # ──────────────────────────────────────────────────────────────────────────

    async def store_metrics(self, metrics: Dict[str, Any]) -> int:
        """
        Inserta las métricas en personality_metrics.

        Retorna el ID de la fila insertada.
        """
        result = await self._db.execute(
            text("""
                INSERT INTO personality_metrics
                    (sarcasm_level, friendliness, verbosity,
                     technical_depth, humor_frequency, sample_size)
                VALUES
                    (:sarcasm_level, :friendliness, :verbosity,
                     :technical_depth, :humor_frequency, :sample_size)
                RETURNING id
            """),
            {
                "sarcasm_level":   metrics["sarcasm_level"],
                "friendliness":    metrics["friendliness"],
                "verbosity":       metrics["verbosity"],
                "technical_depth": metrics["technical_depth"],
                "humor_frequency": metrics["humor_frequency"],
                "sample_size":     metrics["sample_size"],
            },
        )
        row = result.fetchone()
        inserted_id = row[0] if row else -1
        logger.info(f"[personality] métricas guardadas id={inserted_id}")
        return inserted_id

    # ──────────────────────────────────────────────────────────────────────────
    # Lectura
    # ──────────────────────────────────────────────────────────────────────────

    async def get_latest(self) -> Optional[Dict[str, Any]]:
        """Devuelve la última fila de personality_metrics o None si la tabla está vacía."""
        result = await self._db.execute(
            text("""
                SELECT id, timestamp, sarcasm_level, friendliness, verbosity,
                       technical_depth, humor_frequency, sample_size
                FROM personality_metrics
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "id":              row.id,
            "timestamp":       str(row.timestamp),
            "sarcasm_level":   float(row.sarcasm_level   or 0),
            "friendliness":    float(row.friendliness    or 0),
            "verbosity":       float(row.verbosity       or 0),
            "technical_depth": float(row.technical_depth or 0),
            "humor_frequency": float(row.humor_frequency or 0),
            "sample_size":     int(row.sample_size       or 0),
        }

    async def get_history(self, limit: int = 12) -> List[Dict[str, Any]]:
        """Devuelve las últimas `limit` filas de personality_metrics (más reciente primero)."""
        result = await self._db.execute(
            text("""
                SELECT id, timestamp, sarcasm_level, friendliness, verbosity,
                       technical_depth, humor_frequency, sample_size
                FROM personality_metrics
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "id":              r.id,
                "timestamp":       str(r.timestamp),
                "sarcasm_level":   float(r.sarcasm_level   or 0),
                "friendliness":    float(r.friendliness    or 0),
                "verbosity":       float(r.verbosity       or 0),
                "technical_depth": float(r.technical_depth or 0),
                "humor_frequency": float(r.humor_frequency or 0),
                "sample_size":     int(r.sample_size       or 0),
            }
            for r in rows
        ]
