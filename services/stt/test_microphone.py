"""Quick test script to verify STT service is working with a simple audio recording."""
import httpx
import sounddevice as sd
import soundfile as sf
import numpy as np
import tempfile
import os

# Configuration
STT_URL = "http://127.0.0.1:8803"
SAMPLE_RATE = 16000
DURATION = 3  # seconds

def test_stt_health():
    """Test if STT service is ready."""
    print("1. Checking STT service health...")
    try:
        response = httpx.get(f"{STT_URL}/health", timeout=5.0)
        data = response.json()
        print(f"   ✅ Service status: {data['status']}")
        print(f"   ✅ Ready: {data['ready']}")
        print(f"   ✅ Model: {data['model']}")
        print(f"   ✅ Device: {data['device']}")
        return data['ready']
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def record_audio(duration=3):
    """Record audio from microphone."""
    print(f"\n2. Recording {duration} seconds of audio...")
    print("   🎤 Habla ahora...")

    # Record audio
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32'
    )
    sd.wait()

    # Check if audio was captured
    max_amplitude = np.max(np.abs(audio))
    print(f"   ✅ Recording complete. Max amplitude: {max_amplitude:.4f}")

    if max_amplitude < 0.01:
        print("   ⚠️  Warning: Audio muy bajo. Verifica el micrófono.")

    return audio

def save_and_transcribe(audio):
    """Save audio to temp file and transcribe."""
    print("\n3. Saving audio to temporary file...")

    # Create temp WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Save audio
        sf.write(tmp_path, audio, SAMPLE_RATE)
        file_size = os.path.getsize(tmp_path)
        print(f"   ✅ Saved to: {tmp_path}")
        print(f"   ✅ File size: {file_size / 1024:.1f} KB")

        # Transcribe
        print("\n4. Transcribing with STT service...")
        with open(tmp_path, 'rb') as f:
            files = {'file': ('test.wav', f, 'audio/wav')}
            data = {'language': 'es', 'include_timestamps': 'false'}

            response = httpx.post(
                f"{STT_URL}/transcribe",
                files=files,
                data=data,
                timeout=30.0
            )

        if response.status_code == 200:
            result = response.json()
            transcription = result.get('text', '')
            print(f"   ✅ Transcription: \"{transcription}\"")

            if not transcription or transcription.strip() == "":
                print("   ⚠️  Warning: Transcription vacía. Posibles causas:")
                print("      - Audio muy corto")
                print("      - Ruido de fondo filtrado por VAD")
                print("      - Volumen muy bajo")

            return transcription
        else:
            print(f"   ❌ Error {response.status_code}: {response.text}")
            return None

    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            print(f"\n5. Cleaned up temporary file")

def main():
    """Run microphone test."""
    print("=" * 60)
    print("STT Microphone Test")
    print("=" * 60)

    # Check service
    if not test_stt_health():
        print("\n❌ STT service no está listo. Inicia el servicio primero.")
        return

    # Record and transcribe
    audio = record_audio(duration=DURATION)
    transcription = save_and_transcribe(audio)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    if transcription:
        print(f"✅ Success! Transcription: \"{transcription}\"")
    else:
        print("❌ No transcription received")
    print("\nTips para mejor precisión:")
    print("  - Habla claro y a velocidad normal")
    print("  - Mantén 15-20cm de distancia del micrófono")
    print("  - Reduce ruido de fondo")
    print("  - Usa frases completas (no palabras sueltas)")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
