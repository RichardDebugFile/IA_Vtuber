"""
Embedding Service - Generación de vectores para búsqueda semántica.
Si sentence-transformers no está instalado, el servicio arranca igual
pero retorna vectores de ceros (búsqueda semántica desactivada).
"""

import os
from typing import List, Optional
from loguru import logger

# Configuración
EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL",  "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# Importación opcional — no bloquea el arranque si el paquete no está instalado
try:
    import torch
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    logger.warning(
        "sentence-transformers no está instalado. "
        "Los embeddings estarán desactivados (búsqueda semántica retornará vacío). "
        "Instala con: pip install sentence-transformers"
    )


class EmbeddingService:
    """
    Servicio para generar embeddings de texto.
    Usa all-MiniLM-L6-v2 (384 dimensiones) por defecto.
    Degrada gracefully si sentence-transformers no está disponible.
    """

    _instance: Optional["EmbeddingService"] = None
    _model = None   # SentenceTransformer | None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializar modelo de embeddings (solo si la librería está disponible)."""
        if self._model is not None or not _ST_AVAILABLE:
            return

        logger.info(f"Cargando modelo de embeddings: {EMBEDDING_MODEL}")

        if EMBEDDING_DEVICE == "cuda" and torch.cuda.is_available():
            device = "cuda"
            logger.info(f"Usando GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            logger.info("Usando CPU para embeddings")

        try:
            self._model = SentenceTransformer(EMBEDDING_MODEL, device=device)
            logger.info(
                f"Modelo cargado: {EMBEDDING_MODEL} "
                f"({self._model.get_sentence_embedding_dimension()} dims)"
            )
        except Exception as e:
            logger.error(f"Error al cargar modelo de embeddings: {e}")
            # No re-raise: el servicio arranca sin embeddings

    @property
    def available(self) -> bool:
        """True si el modelo está listo para generar embeddings."""
        return self._model is not None

    def encode(self, text: str) -> List[float]:
        """
        Genera embedding para un texto.
        Retorna vector de ceros si el modelo no está disponible.
        """
        if not self.available:
            return [0.0] * 384

        if not text or not text.strip():
            return [0.0] * 384

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return [0.0] * 384

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos.
        Retorna lista de ceros si el modelo no está disponible.
        """
        if not texts:
            return []

        if not self.available:
            return [[0.0] * 384 for _ in texts]

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 100,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error al generar embeddings batch: {e}")
            return [[0.0] * 384 for _ in texts]

    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calcula similitud coseno entre dos embeddings."""
        import numpy as np

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def get_dimension(self) -> int:
        """Dimensión de los embeddings (384 por defecto)."""
        if self._model is not None:
            return self._model.get_sentence_embedding_dimension()
        return 384


# Instancia global singleton
embedding_service = EmbeddingService()
