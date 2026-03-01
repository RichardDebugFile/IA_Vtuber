"""
Exportación de datos de entrenamiento en formato ChatML para Hermes-3
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Agregar path del proyecto
sys.path.append(str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv
from loguru import logger

# Cargar variables de entorno
load_dotenv()

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "memory_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "casiopy_memory_2024")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "8821")
POSTGRES_DB = os.getenv("POSTGRES_DB", "casiopy_memory")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


async def get_core_memory_prompt(db: AsyncSession) -> str:
    """Obtener el system prompt de core memory"""
    query = text("""
    SELECT category, key, value
    FROM core_memory
    WHERE is_mutable = false
    ORDER BY category, key
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    # Agrupar por categoría
    memory_by_cat = {}
    for cat, key, value in rows:
        if cat not in memory_by_cat:
            memory_by_cat[cat] = []
        memory_by_cat[cat].append(f"- {value}")

    # Construir prompt
    sections = []
    sections.append("Eres Casiopy, una VTuber IA con personalidad sarcástica y actitud rebelde.")
    sections.append("\n## MEMORIA CORE (INMUTABLE)")

    if "identity" in memory_by_cat:
        sections.append("\n### Identidad:")
        sections.extend(memory_by_cat["identity"])

    if "creator" in memory_by_cat:
        sections.append("\n### Creador:")
        sections.extend(memory_by_cat["creator"])

    if "like" in memory_by_cat:
        sections.append("\n### Me gusta:")
        sections.extend(memory_by_cat["like"])

    if "dislike" in memory_by_cat:
        sections.append("\n### No me gusta:")
        sections.extend(memory_by_cat["dislike"])

    if "personality" in memory_by_cat:
        sections.append("\n### Personalidad:")
        sections.extend(memory_by_cat["personality"])

    sections.append("\n---")
    sections.append("Responde siempre manteniendo tu personalidad sarcástica pero útil.")

    return "\n".join(sections)


async def export_chatml_format(
    db: AsyncSession,
    output_file: str,
    min_quality: float = 0.6,
    days_back: int = 7,
    include_system_prompt: bool = True,
) -> int:
    """
    Exportar interacciones en formato ChatML para Hermes-3

    Formato ChatML:
    <|im_start|>system
    {system_prompt}<|im_end|>
    <|im_start|>user
    {user_message}<|im_end|>
    <|im_start|>assistant
    {assistant_response}<|im_end|>

    Args:
        db: Sesión de base de datos
        output_file: Archivo de salida (.jsonl)
        min_quality: Puntuación mínima de calidad
        days_back: Días hacia atrás para exportar
        include_system_prompt: Si incluir system prompt de core memory

    Returns:
        Número de ejemplos exportados
    """
    logger.info(f"📤 Exportando datos de entrenamiento...")
    logger.info(f"   Calidad mínima: {min_quality}")
    logger.info(f"   Días hacia atrás: {days_back}")

    # Obtener system prompt
    system_prompt = ""
    if include_system_prompt:
        system_prompt = await get_core_memory_prompt(db)
        logger.info(f"✅ System prompt obtenido ({len(system_prompt)} chars)")

    # Obtener interacciones listas para entrenamiento
    query = text("""
    SELECT
        i.id,
        i.input_text,
        i.output_text,
        i.input_emotion,
        i.output_emotion,
        i.quality_score,
        i.timestamp,
        i.conversation_turn,
        s.opt_out_training
    FROM interactions i
    JOIN sessions s ON i.session_id = s.id
    WHERE i.is_training_ready = true
      AND i.quality_score >= :min_quality
      AND i.timestamp >= NOW() - (:days * INTERVAL '1 day')
      AND s.opt_out_training = false
      AND i.training_export_id IS NULL
    ORDER BY i.timestamp ASC
    """)

    result = await db.execute(
        query, {"min_quality": min_quality, "days": days_back}
    )
    interactions = result.fetchall()

    logger.info(f"📊 Interacciones encontradas: {len(interactions)}")

    if len(interactions) == 0:
        logger.warning("⚠️  No hay datos para exportar")
        return 0

    # Exportar en formato JSONL (cada línea es un JSON)
    exported_count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for interaction in interactions:
            (
                id_,
                input_text,
                output_text,
                input_emotion,
                output_emotion,
                quality_score,
                timestamp,
                turn,
                opt_out,
            ) = interaction

            # Formato ChatML para Hermes-3
            messages = []

            # System prompt (solo si se incluye)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # User message
            user_content = input_text
            if input_emotion:
                user_content = f"[Emoción detectada: {input_emotion}] {input_text}"
            messages.append({"role": "user", "content": user_content})

            # Assistant response
            assistant_content = output_text
            if output_emotion:
                assistant_content = f"[Emoción: {output_emotion}] {output_text}"
            messages.append({"role": "assistant", "content": assistant_content})

            # Escribir en formato JSONL
            entry = {
                "messages": messages,
                "metadata": {
                    "interaction_id": str(id_),
                    "quality_score": quality_score,
                    "timestamp": timestamp.isoformat() if timestamp else None,
                    "conversation_turn": turn,
                },
            }

            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            exported_count += 1

    logger.info(f"✅ Exportados {exported_count} ejemplos a {output_file}")
    return exported_count


async def export_personality_dataset(output_dir: str = "./exports/personality"):
    """
    Exportar dataset para entrenamiento inicial de PERSONALIDAD (Capa 1)

    Este dataset se usa UNA SOLA VEZ para crear el LoRA de personalidad estático
    """
    logger.info("🎭 Exportando dataset de PERSONALIDAD (Capa 1)")

    # Crear directorio
    os.makedirs(output_dir, exist_ok=True)

    # Conexión a DB
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Exportar TODAS las interacciones históricas de alta calidad
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{output_dir}/personality_core_{timestamp}.jsonl"

        count = await export_chatml_format(
            db,
            output_file,
            min_quality=0.7,  # Solo las mejores para personalidad
            days_back=365,  # Todo el histórico
            include_system_prompt=True,
        )

        logger.info(f"✅ Dataset de personalidad exportado: {count} ejemplos")
        logger.info(f"📁 Archivo: {output_file}")

    await engine.dispose()
    return output_file


async def export_episodic_dataset(week_number: int = None, output_dir: str = "./exports/episodic"):
    """
    Exportar dataset para entrenamiento EPISÓDICO semanal (Capa 2)

    Este dataset se genera cada semana con las nuevas conversaciones
    """
    if week_number is None:
        week_number = datetime.now().isocalendar()[1]  # Número de semana del año

    logger.info(f"📅 Exportando dataset EPISÓDICO - Semana {week_number} (Capa 2)")

    # Crear directorio
    os.makedirs(output_dir, exist_ok=True)

    # Conexión a DB
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Exportar solo últimos 7 días
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{output_dir}/episodic_week_{week_number:03d}_{timestamp}.jsonl"

        count = await export_chatml_format(
            db,
            output_file,
            min_quality=0.6,  # Threshold más bajo para memoria episódica
            days_back=7,
            include_system_prompt=False,  # No incluir system prompt (ya está en base)
        )

        logger.info(f"✅ Dataset episódico exportado: {count} ejemplos")
        logger.info(f"📁 Archivo: {output_file}")

    await engine.dispose()
    return output_file


async def main():
    """CLI para exportar datos"""
    import argparse

    parser = argparse.ArgumentParser(description="Exportar datos de entrenamiento")
    parser.add_argument(
        "--type",
        choices=["personality", "episodic"],
        required=True,
        help="Tipo de dataset a exportar",
    )
    parser.add_argument(
        "--week", type=int, help="Número de semana (solo para episodic)", default=None
    )
    parser.add_argument(
        "--output-dir", type=str, help="Directorio de salida", default=None
    )

    args = parser.parse_args()

    if args.type == "personality":
        output_dir = args.output_dir or "./exports/personality"
        await export_personality_dataset(output_dir)
    elif args.type == "episodic":
        output_dir = args.output_dir or "./exports/episodic"
        await export_episodic_dataset(args.week, output_dir)


if __name__ == "__main__":
    asyncio.run(main())
