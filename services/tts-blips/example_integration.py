"""Example integration of blips with the IA VTuber system."""
import asyncio
import base64
from pathlib import Path

import httpx


class BlipsClient:
    """Simple HTTP client for the blips service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8803"):
        self.base_url = base_url

    async def generate(
        self,
        text: str,
        emotion: str = "neutral",
        speed: float = 20.0,
    ) -> bytes:
        """Generate blips audio for text.

        Args:
            text: Text to generate blips for
            emotion: Emotion for voice modulation
            speed: Blips per second

        Returns:
            WAV audio bytes
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/blips/generate",
                json={
                    "text": text,
                    "emotion": emotion,
                    "speed": speed,
                },
            )
            response.raise_for_status()
            data = response.json()
            return base64.b64decode(data["audio_b64"])

    async def health(self) -> bool:
        """Check if blips service is healthy."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# Example 1: Parallel blips + TTS
async def example_parallel_blips_tts():
    """Use blips while TTS processes in background."""
    print("\n[Example 1] Parallel Blips + TTS\n")

    blips_client = BlipsClient()

    # Check if service is running
    if not await blips_client.health():
        print("ERROR: Blips service not running. Start with:")
        print("  cd services/tts-blips")
        print("  ../../venv/Scripts/python.exe -m src.server")
        return

    text = "Hola, estoy procesando tu solicitud"
    emotion = "neutral"

    # Start TTS in background (simulated with sleep)
    async def fake_tts():
        await asyncio.sleep(3.0)  # Simulate TTS taking 3 seconds
        return b"<tts_audio_bytes>"

    # Generate blips immediately
    print(f"Generating blips for: '{text}'")
    blips_audio = await blips_client.generate(text, emotion, speed=20.0)

    # Save blips
    output_file = Path("example_blips.wav")
    output_file.write_bytes(blips_audio)
    print(f"[OK] Blips generated: {output_file} ({len(blips_audio)} bytes)")
    print("     -> Play this while waiting for TTS")

    # Wait for TTS
    print("Waiting for TTS to finish...")
    tts_audio = await fake_tts()
    print(f"[OK] TTS finished: {len(tts_audio)} bytes")
    print("     -> Now switch from blips to TTS audio")


# Example 2: Fallback when TTS is slow
async def example_fallback_blips():
    """Use blips as fallback when TTS is slow."""
    print("\n[Example 2] Fallback Blips (when TTS > 2s)\n")

    blips_client = BlipsClient()

    if not await blips_client.health():
        print("ERROR: Blips service not running")
        return

    text = "Este es un mensaje largo que podría tardar en procesarse"
    emotion = "thinking"

    # Simulate slow TTS
    async def slow_tts():
        await asyncio.sleep(4.0)  # Slow TTS
        return b"<tts_audio_bytes>"

    # Start TTS
    tts_task = asyncio.create_task(slow_tts())

    # Wait up to 2 seconds
    try:
        tts_audio = await asyncio.wait_for(tts_task, timeout=2.0)
        print(f"[OK] TTS finished quickly: {len(tts_audio)} bytes")
    except asyncio.TimeoutError:
        print("[WARN] TTS taking too long (>2s), using blips as fallback")

        # Generate blips as fallback
        blips_audio = await blips_client.generate(text, emotion, speed=18.0)
        output_file = Path("example_fallback.wav")
        output_file.write_bytes(blips_audio)
        print(f"[OK] Blips fallback: {output_file} ({len(blips_audio)} bytes)")

        # Still wait for TTS to finish in background
        tts_audio = await tts_task
        print(f"[OK] TTS eventually finished: {len(tts_audio)} bytes")


# Example 3: Emotion-aware blips
async def example_emotion_blips():
    """Generate blips with different emotions."""
    print("\n[Example 3] Emotion-Aware Blips\n")

    blips_client = BlipsClient()

    if not await blips_client.health():
        print("ERROR: Blips service not running")
        return

    # Different emotional messages
    messages = [
        ("¡Genial! Completamos la tarea", "excited"),
        ("Lo siento, hubo un error", "sad"),
        ("¡Cuidado con eso!", "fear"),
        ("Déjame pensar un momento...", "thinking"),
    ]

    for text, emotion in messages:
        blips_audio = await blips_client.generate(text, emotion, speed=20.0)
        output_file = Path(f"example_{emotion}.wav")
        output_file.write_bytes(blips_audio)
        print(f"[{emotion:10s}] {text:40s} -> {output_file}")


# Run examples
async def main():
    """Run all examples."""
    print("=" * 70)
    print("TTS Blips - Integration Examples")
    print("=" * 70)

    await example_parallel_blips_tts()
    await example_fallback_blips()
    await example_emotion_blips()

    print("\n" + "=" * 70)
    print("[SUCCESS] All examples completed!")
    print("=" * 70)
    print("\nGenerated audio files:")
    print("  - example_blips.wav (parallel example)")
    print("  - example_fallback.wav (fallback example)")
    print("  - example_*.wav (emotion examples)")
    print("\nTo start the blips server:")
    print("  cd services/tts-blips")
    print("  ../../venv/Scripts/python.exe -m src.server")


if __name__ == "__main__":
    asyncio.run(main())
