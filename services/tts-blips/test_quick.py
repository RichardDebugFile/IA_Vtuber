"""Quick test script for blip generator."""
import base64
from pathlib import Path

from src.blip_generator import BlipGenerator
from src.voice_config import get_voice_for_emotion

# Create output directory
output_dir = Path("test_outputs")
output_dir.mkdir(exist_ok=True)

# Initialize generator
print("Initializing BlipGenerator...")
generator = BlipGenerator(sample_rate=44100)

# Test 1: Single blip preview
print("\n[Test 1] Generating single blips for different characters...")
for char in ["a", "s", "m"]:
    wav_bytes = generator.generate_single_blip(char=char, emotion="neutral")
    output_file = output_dir / f"blip_{char}.wav"
    output_file.write_bytes(wav_bytes)
    print(f"  [OK] Generated {output_file} ({len(wav_bytes)} bytes)")

# Test 2: Text blips with different emotions
print("\n[Test 2] Generating text blips with different emotions...")
test_texts = [
    ("Hola mundo", "neutral"),
    ("¡Estoy muy feliz!", "happy"),
    ("Qué tristeza...", "sad"),
    ("¡No puedo creerlo!", "excited"),
    ("Esto me molesta", "angry"),
]

for text, emotion in test_texts:
    wav_bytes, duration_ms, num_blips = generator.generate_text_blips(
        text=text,
        emotion=emotion,
        blips_per_second=20.0,
    )
    output_file = output_dir / f"text_{emotion}.wav"
    output_file.write_bytes(wav_bytes)
    print(f"  [OK] {emotion:10s} | {text:25s} | {num_blips:2d} blips | {duration_ms:4d}ms | {output_file}")

# Test 3: Different speeds
print("\n[Test 3] Testing different speeds...")
text = "Prueba de velocidad"
for speed in [10.0, 20.0, 30.0]:
    wav_bytes, duration_ms, num_blips = generator.generate_text_blips(
        text=text,
        emotion="neutral",
        blips_per_second=speed,
    )
    output_file = output_dir / f"speed_{int(speed)}.wav"
    output_file.write_bytes(wav_bytes)
    print(f"  [OK] {speed:5.1f} blips/s | {duration_ms:4d}ms | {output_file}")

# Test 4: Voice profiles
print("\n[Test 4] Voice profile characteristics...")
for emotion in ["neutral", "happy", "sad", "excited", "angry"]:
    voice = get_voice_for_emotion(emotion)
    print(f"  {emotion:10s} | Pitch: {voice.base_pitch:6.1f}Hz | Duration: {voice.duration_ms:5.1f}ms | Amplitude: {voice.amplitude:.2f}")

print(f"\n[SUCCESS] All tests completed! Check {output_dir}/ for generated audio files.")
print("\nTo play the audio files, you can use:")
print(f"  - Windows: start {output_dir}/text_happy.wav")
print(f"  - Python: python -m wave {output_dir}/text_happy.wav")
