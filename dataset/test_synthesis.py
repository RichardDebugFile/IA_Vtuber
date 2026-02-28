"""Test TTS synthesis with sample phrases."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.tts_client import TTSClient


async def test_phrases():
    """Test synthesis with various phrase lengths."""

    # Test phrases of different lengths
    test_phrases = [
        "Buenos días a todos, espero que hayan descansado muy bien",  # 10 words
        "Ajusta los parámetros hasta encontrar la configuración óptima que nos dé los mejores resultados posibles",  # 15 words
        "Qué cansancio tan profundo siento en todo mi cuerpo, apenas puedo mantenerme despierta ahora",  # 15 words
        "En aquel lugar tan lejano había una historia increíble esperando ser descubierta por alguien",  # 15 words
    ]

    client = TTSClient()

    # Check health first
    print("Verificando conexión con TTS service...")
    healthy = await client.check_health()
    if not healthy:
        print("❌ ERROR: TTS service no está disponible en http://127.0.0.1:8802")
        print("   Asegúrate de que el servicio TTS esté ejecutándose.")
        return

    print("✓ TTS service está disponible\n")

    # Test each phrase
    for i, phrase in enumerate(test_phrases, 1):
        word_count = len(phrase.split())
        print(f"Test {i}: {phrase[:60]}... ({word_count} palabras)")

        try:
            audio = await client.synthesize(phrase, backend="http")

            if audio:
                print(f"  ✓ Síntesis exitosa: {len(audio)} bytes")
            else:
                print(f"  ❌ Síntesis falló: No se recibió audio")
        except Exception as e:
            print(f"  ❌ Error durante síntesis: {e}")

        print()
        await asyncio.sleep(1)  # Small delay between tests

    await client.close()


if __name__ == "__main__":
    print("=== Test de Síntesis TTS ===\n")
    asyncio.run(test_phrases())
