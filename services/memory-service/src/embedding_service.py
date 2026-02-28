"""
Embedding Service - Generación de vectores para búsqueda semántica
"""

import os
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from loguru import logger
import torch

# Configuración
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")


class EmbeddingService:
    """
    Servicio para generar embeddings de texto
    Usa all-MiniLM-L6-v2 (384 dimensiones) por defecto
    """

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializar modelo de embeddings"""
        if self._model is None:
            logger.info(f"🔄 Cargando modelo de embeddings: {EMBEDDING_MODEL}")

            # Determinar device
            if EMBEDDING_DEVICE == "cuda" and torch.cuda.is_available():
                device = "cuda"
                logger.info(f"✅ Usando GPU: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                logger.info("✅ Usando CPU para embeddings")

            try:
                self._model = SentenceTransformer(EMBEDDING_MODEL, device=device)
                logger.info(f"✅ Modelo cargado: {EMBEDDING_MODEL}")
                logger.info(f"   Dimensiones: {self._model.get_sentence_embedding_dimension()}")
            except Exception as e:
                logger.error(f"❌ Error al cargar modelo de embeddings: {e}")
                raise

    def encode(self, text: str) -> List[float]:
        """
        Generar embedding para un texto

        Args:
            text: Texto a codificar

        Returns:
            Vector de embeddings (384 dimensiones)
        """
        if not text or not text.strip():
            logger.warning("⚠️  Texto vacío, retornando vector de ceros")
            return [0.0] * 384

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Error al generar embedding: {e}")
            return [0.0] * 384

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generar embeddings para múltiples textos

        Args:
            texts: Lista de textos
            batch_size: Tamaño del batch para procesamiento

        Returns:
            Lista de vectores de embeddings
        """
        if not texts:
            return []

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 100,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"❌ Error al generar embeddings batch: {e}")
            return [[0.0] * 384 for _ in texts]

    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calcular similitud coseno entre dos embeddings

        Args:
            embedding1: Primer embedding
            embedding2: Segundo embedding

        Returns:
            Similitud coseno (0-1)
        """
        import numpy as np

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def get_dimension(self) -> int:
        """Obtener dimensión de los embeddings"""
        return self._model.get_sentence_embedding_dimension()


# Instancia global
embedding_service = EmbeddingService()
