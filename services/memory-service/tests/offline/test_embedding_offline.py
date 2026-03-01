"""
Tests offline de EmbeddingService (sin servicios ni BD).

Carga el modelo all-MiniLM-L6-v2 directamente.

Ejecutar:
  cd services/memory-service
  python -m pytest tests/offline/test_embedding_offline.py -v
"""

import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class TestEmbeddingServiceOffline:
    """Valida EmbeddingService directamente (carga el modelo localmente)."""

    @pytest.fixture(scope="class")
    def svc(self):
        from embedding_service import EmbeddingService
        return EmbeddingService()

    def test_encode_returns_384_dims(self, svc):
        vec = svc.encode("Hola, soy Casiopy")
        assert len(vec) == 384, f"Esperados 384 dims, obtenidos {len(vec)}"

    def test_empty_text_returns_zeros(self, svc):
        vec = svc.encode("")
        assert all(v == 0.0 for v in vec), "Texto vacío debe retornar vector de ceros"
        assert len(vec) == 384

    def test_batch_equals_single(self, svc):
        texts = ["Hola mundo", "Me gusta el anime"]
        batch = svc.encode_batch(texts)
        singles = [svc.encode(t) for t in texts]
        for b, s in zip(batch, singles):
            for bv, sv in zip(b, s):
                assert abs(bv - sv) < 1e-5, "encode_batch debe coincidir con llamadas individuales"

    def test_identical_texts_similarity_above_0_99(self, svc):
        t = "Casiopy es la mejor VTuber"
        v1 = svc.encode(t)
        v2 = svc.encode(t)
        sim = svc.similarity(v1, v2)
        assert sim > 0.99, f"Textos idénticos deben tener similitud > 0.99, obtenido {sim}"

    def test_unrelated_texts_similarity_below_0_5(self, svc):
        v1 = svc.encode("Me gusta el ramen japonés")
        v2 = svc.encode("El teorema de Pitágoras dice que a²+b²=c²")
        sim = svc.similarity(v1, v2)
        assert sim < 0.5, f"Textos no relacionados deben tener similitud < 0.5, obtenido {sim}"

    def test_related_texts_similarity_above_0_5(self, svc):
        # all-MiniLM-L6-v2 está entrenado principalmente en inglés;
        # paráfrasis en español obtienen ~0.55-0.65 (umbral realista > 0.5)
        v1 = svc.encode("¿Cuál es tu videojuego favorito?")
        v2 = svc.encode("¿Qué juego te gusta más?")
        sim = svc.similarity(v1, v2)
        assert sim > 0.5, (
            f"Textos relacionados deben tener similitud > 0.5, obtenido {sim}"
        )
