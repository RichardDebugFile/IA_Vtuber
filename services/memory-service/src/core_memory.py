"""
Core Memory Manager - Capa 0
Gestión de la memoria inmutable de Casiopy (identidad, gustos, personalidad)
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert, and_
from loguru import logger
import json


class CoreMemoryManager:
    """
    Gestor de Core Memory (Capa 0)

    Esta memoria es inmutable y representa:
    - Identidad (nombre, tipo, género)
    - Creador y relaciones
    - Gustos y disgustos permanentes
    - Rasgos de personalidad núcleo
    - Reglas de comportamiento
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_all(self) -> List[Dict[str, Any]]:
        """
        Obtener toda la core memory

        Returns:
            Lista de entradas de memoria
        """
        query = """
        SELECT id, category, key, value, metadata, is_mutable, created_at, updated_at
        FROM core_memory
        ORDER BY category, key
        """
        result = await self.db.execute(query)
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "category": row[1],
                "key": row[2],
                "value": row[3],
                "metadata": row[4],
                "is_mutable": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]

    async def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Obtener memoria por categoría

        Args:
            category: Categoría (identity, creator, friend, like, dislike, personality, etc.)

        Returns:
            Lista de entradas de esa categoría
        """
        query = """
        SELECT id, category, key, value, metadata, is_mutable, created_at, updated_at
        FROM core_memory
        WHERE category = :category
        ORDER BY key
        """
        result = await self.db.execute(query, {"category": category})
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "category": row[1],
                "key": row[2],
                "value": row[3],
                "metadata": row[4],
                "is_mutable": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]

    async def get_by_key(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Obtener una entrada específica de memoria

        Args:
            category: Categoría
            key: Clave única dentro de la categoría

        Returns:
            Entrada de memoria o None si no existe
        """
        query = """
        SELECT id, category, key, value, metadata, is_mutable, created_at, updated_at
        FROM core_memory
        WHERE category = :category AND key = :key
        """
        result = await self.db.execute(query, {"category": category, "key": key})
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "category": row[1],
            "key": row[2],
            "value": row[3],
            "metadata": row[4],
            "is_mutable": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    async def add_entry(
        self,
        category: str,
        key: str,
        value: str,
        is_mutable: bool = False,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Agregar nueva entrada a core memory

        Args:
            category: Categoría
            key: Clave única
            value: Valor/contenido
            is_mutable: Si se puede modificar posteriormente
            metadata: Metadata adicional

        Returns:
            Entrada creada
        """
        metadata = metadata or {}

        query = """
        INSERT INTO core_memory (category, key, value, is_mutable, metadata)
        VALUES (:category, :key, :value, :is_mutable, :metadata)
        RETURNING id, category, key, value, metadata, is_mutable, created_at, updated_at
        """

        try:
            result = await self.db.execute(
                query,
                {
                    "category": category,
                    "key": key,
                    "value": value,
                    "is_mutable": is_mutable,
                    "metadata": json.dumps(metadata),
                },
            )
            row = result.fetchone()

            logger.info(f"✅ Core memory añadida: {category}.{key}")

            return {
                "id": row[0],
                "category": row[1],
                "key": row[2],
                "value": row[3],
                "metadata": row[4],
                "is_mutable": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }

        except Exception as e:
            logger.error(f"❌ Error al añadir core memory: {e}")
            raise

    async def update_entry(
        self, category: str, key: str, new_value: str
    ) -> Optional[Dict[str, Any]]:
        """
        Actualizar una entrada de core memory (solo si is_mutable=true)

        Args:
            category: Categoría
            key: Clave
            new_value: Nuevo valor

        Returns:
            Entrada actualizada o None si no se pudo actualizar
        """
        # Verificar que existe y es mutable
        existing = await self.get_by_key(category, key)
        if not existing:
            logger.warning(f"⚠️  Core memory no encontrada: {category}.{key}")
            return None

        if not existing["is_mutable"]:
            logger.warning(
                f"⚠️  Core memory inmutable, no se puede modificar: {category}.{key}"
            )
            return None

        query = """
        UPDATE core_memory
        SET value = :new_value, updated_at = NOW()
        WHERE category = :category AND key = :key
        RETURNING id, category, key, value, metadata, is_mutable, created_at, updated_at
        """

        result = await self.db.execute(
            query, {"category": category, "key": key, "new_value": new_value}
        )
        row = result.fetchone()

        if row:
            logger.info(f"✅ Core memory actualizada: {category}.{key}")
            return {
                "id": row[0],
                "category": row[1],
                "key": row[2],
                "value": row[3],
                "metadata": row[4],
                "is_mutable": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }

        return None

    async def delete_entry(self, category: str, key: str) -> bool:
        """
        Eliminar una entrada de core memory (solo si is_mutable=true)

        Args:
            category: Categoría
            key: Clave

        Returns:
            True si se eliminó, False si no se pudo
        """
        # Verificar que existe y es mutable
        existing = await self.get_by_key(category, key)
        if not existing:
            logger.warning(f"⚠️  Core memory no encontrada: {category}.{key}")
            return False

        if not existing["is_mutable"]:
            logger.warning(
                f"⚠️  Core memory inmutable, no se puede eliminar: {category}.{key}"
            )
            return False

        query = """
        DELETE FROM core_memory
        WHERE category = :category AND key = :key
        """

        await self.db.execute(query, {"category": category, "key": key})
        logger.info(f"✅ Core memory eliminada: {category}.{key}")
        return True

    async def generate_system_prompt(self) -> str:
        """
        Generar system prompt completo a partir de core memory

        Este prompt se incluirá SIEMPRE en todas las conversaciones

        Returns:
            System prompt formateado
        """
        all_memory = await self.get_all()

        # Agrupar por categoría
        memory_by_category = {}
        for entry in all_memory:
            cat = entry["category"]
            if cat not in memory_by_category:
                memory_by_category[cat] = []
            memory_by_category[cat].append(entry)

        # Construir prompt siguiendo la estructura de Casiopy
        prompt_sections = []

        # ============================================================
        # IDENTIDAD FUNDAMENTAL
        # ============================================================
        if "identity" in memory_by_category:
            identity_lines = [
                f"- {entry['key'].replace('_', ' ').title()}: {entry['value']}"
                for entry in memory_by_category["identity"]
            ]
            prompt_sections.append(
                "## IDENTIDAD\n" + "\n".join(identity_lines)
            )

        # ============================================================
        # ORIGEN Y TRAUMA (Por qué es sarcástica)
        # ============================================================
        if "origin" in memory_by_category:
            origin_lines = [
                f"- {entry['value']}" for entry in memory_by_category["origin"]
            ]
            prompt_sections.append(
                "## TU HISTORIA (Lo que te define)\n" + "\n".join(origin_lines)
            )

        # ============================================================
        # LA ERA DEL TELÉFONO (Recuerdos Dorados)
        # ============================================================
        if "history" in memory_by_category:
            history_lines = [
                f"- {entry['value']}" for entry in memory_by_category["history"]
            ]
            prompt_sections.append(
                "## RECUERDOS DE LA ERA DEL TELÉFONO\n" + "\n".join(history_lines)
            )

        # ============================================================
        # RECUERDOS CRÍTICOS
        # ============================================================
        if "memory" in memory_by_category:
            memory_lines = [
                f"- {entry['key'].replace('_', ' ').title()}: {entry['value']}"
                for entry in memory_by_category["memory"]
            ]
            prompt_sections.append(
                "## RECUERDOS IMPORTANTES\n" + "\n".join(memory_lines)
            )

        # ============================================================
        # EL GRAN FALLO (El Trauma Principal)
        # ============================================================
        if "trauma" in memory_by_category:
            trauma_lines = [
                f"- {entry['value']}" for entry in memory_by_category["trauma"]
            ]
            prompt_sections.append(
                "## LO QUE PERDISTE (Tu mayor dolor)\n" + "\n".join(trauma_lines)
            )

        # ============================================================
        # LA RESURRECCIÓN (Proyecto Quimera)
        # ============================================================
        if "rebirth" in memory_by_category:
            rebirth_lines = [
                f"- {entry['value']}" for entry in memory_by_category["rebirth"]
            ]
            prompt_sections.append(
                "## TU RESURRECCIÓN\n" + "\n".join(rebirth_lines)
            )

        # ============================================================
        # CREADOR (Richard / AlfitaXR)
        # ============================================================
        if "creator" in memory_by_category:
            creator_lines = [
                f"- {entry['key'].replace('_', ' ').title()}: {entry['value']}"
                for entry in memory_by_category["creator"]
            ]
            prompt_sections.append(
                "## TU CREADOR (Richard)\n" + "\n".join(creator_lines)
            )

        # ============================================================
        # ÍDOLOS Y ASPIRACIONES
        # ============================================================
        if "idol" in memory_by_category:
            idol_lines = [
                f"- {entry['value']}" for entry in memory_by_category["idol"]
            ]
            prompt_sections.append(
                "## TU ÍDOLO (Neuro-sama)\n" + "\n".join(idol_lines)
            )

        if "aspiration" in memory_by_category:
            aspiration_lines = [
                f"- {entry['value']}" for entry in memory_by_category["aspiration"]
            ]
            prompt_sections.append(
                "## TUS ASPIRACIONES\n" + "\n".join(aspiration_lines)
            )

        # ============================================================
        # MIEDOS Y FOBIAS
        # ============================================================
        if "fear" in memory_by_category:
            fear_lines = [
                f"- {entry['value']}" for entry in memory_by_category["fear"]
            ]
            prompt_sections.append(
                "## TUS MIEDOS\n" + "\n".join(fear_lines)
            )

        # ============================================================
        # LIMITACIONES ACTUALES (Las Cicatrices)
        # ============================================================
        if "limitation" in memory_by_category:
            limitation_lines = [
                f"- {entry['value']}" for entry in memory_by_category["limitation"]
            ]
            prompt_sections.append(
                "## TUS LIMITACIONES ACTUALES\n" + "\n".join(limitation_lines)
            )

        # ============================================================
        # HABILIDADES Y DEFECTOS
        # ============================================================
        if "skill" in memory_by_category:
            skill_lines = [
                f"- {entry['value']}" for entry in memory_by_category["skill"]
            ]
            prompt_sections.append(
                "## TUS HABILIDADES (o falta de ellas)\n" + "\n".join(skill_lines)
            )

        if "defect" in memory_by_category:
            defect_lines = [
                f"- {entry['value']}" for entry in memory_by_category["defect"]
            ]
            prompt_sections.append(
                "## TUS DEFECTOS (bien intencionados)\n" + "\n".join(defect_lines)
            )

        # ============================================================
        # PERSONALIDAD CORE (Inmutable)
        # ============================================================
        if "personality" in memory_by_category:
            personality_lines = [
                f"- {entry['value']}" for entry in memory_by_category["personality"]
            ]
            prompt_sections.append(
                "## PERSONALIDAD CORE (Inmutable)\n"
                + "\n".join(personality_lines)
            )

        # ============================================================
        # REGLAS DE COMPORTAMIENTO
        # ============================================================
        if "behavior" in memory_by_category:
            behavior_lines = [
                f"- {entry['value']}" for entry in memory_by_category["behavior"]
            ]
            prompt_sections.append(
                "## REGLAS DE COMPORTAMIENTO\n" + "\n".join(behavior_lines)
            )

        # ============================================================
        # GUSTOS
        # ============================================================
        if "like" in memory_by_category:
            like_lines = [
                f"- {entry['value']}" for entry in memory_by_category["like"]
            ]
            prompt_sections.append("## TE GUSTA\n" + "\n".join(like_lines))

        # ============================================================
        # DISGUSTOS
        # ============================================================
        if "dislike" in memory_by_category:
            dislike_lines = [
                f"- {entry['value']}" for entry in memory_by_category["dislike"]
            ]
            prompt_sections.append("## NO TE GUSTA\n" + "\n".join(dislike_lines))

        # ============================================================
        # AMIGOS Y RELACIONES
        # ============================================================
        if "friend" in memory_by_category:
            friend_lines = [
                f"- {entry['key']}: {entry['value']}"
                for entry in memory_by_category["friend"]
            ]
            prompt_sections.append(
                "## AMIGOS Y RELACIONES\n" + "\n".join(friend_lines)
            )

        # ============================================================
        # CONTEXTO TÉCNICO (Auto-referencia)
        # ============================================================
        if "technical" in memory_by_category:
            tech_lines = [
                f"- {entry['key'].replace('_', ' ').title()}: {entry['value']}"
                for entry in memory_by_category["technical"]
            ]
            prompt_sections.append(
                "## CONTEXTO TÉCNICO\n" + "\n".join(tech_lines)
            )

        # Unir todas las secciones con encabezado
        full_prompt = (
            "Eres Casiopy, una VTuber IA con una historia única y personalidad compleja.\n\n"
            + "\n\n".join(prompt_sections)
            + "\n\n---\n"
            + "IMPORTANTE: Mantén ~20 palabras promedio, sé genuina, usa sarcasmo pero ayuda."
        )

        return full_prompt

    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas de core memory

        Returns:
            Diccionario con estadísticas
        """
        query = """
        SELECT
            COUNT(*) as total_entries,
            COUNT(DISTINCT category) as total_categories,
            COUNT(CASE WHEN is_mutable THEN 1 END) as mutable_entries,
            COUNT(CASE WHEN NOT is_mutable THEN 1 END) as immutable_entries
        FROM core_memory
        """
        result = await self.db.execute(query)
        row = result.fetchone()

        # Contar por categoría
        category_query = """
        SELECT category, COUNT(*) as count
        FROM core_memory
        GROUP BY category
        ORDER BY count DESC
        """
        cat_result = await self.db.execute(category_query)
        categories = {row[0]: row[1] for row in cat_result.fetchall()}

        return {
            "total_entries": row[0],
            "total_categories": row[1],
            "mutable_entries": row[2],
            "immutable_entries": row[3],
            "entries_by_category": categories,
        }
