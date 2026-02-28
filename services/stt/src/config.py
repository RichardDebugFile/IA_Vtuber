"""Configuration for STT service."""
import os
from typing import Literal

# Whisper model configuration
# Using 'medium' for high accuracy (needed for better Spanish recognition)
# base: 74M params, fast but less accurate (~75% accuracy)
# small: 244M params, good balance (~85% accuracy)
# medium: 769M params, very accurate but slower (~92% accuracy) - CURRENT
# large-v3: 1550M params, best accuracy (~95% accuracy)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")  # tiny, base, small, medium, large-v3
DEVICE = os.getenv("DEVICE", "auto")  # auto, cpu, cuda
LANGUAGE = os.getenv("LANGUAGE", "es")  # es, en, auto
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float32")  # int8, float16, float32 (float32 for compatibility, float16 for GPU)

# Service configuration
STT_PORT = int(os.getenv("STT_PORT", "8803"))
HOST = os.getenv("STT_HOST", "127.0.0.1")

# VAD (Voice Activity Detection) configuration
VAD_CONFIG = {
    "threshold": 0.5,       # Threshold for voice detection (0.0-1.0)
    "min_silence_ms": 300,  # Minimum silence duration to split phrases (ms)
    "min_speech_ms": 250,   # Minimum valid speech duration (ms)
}

# Transcription settings
# Optimized for accuracy in Spanish conversational speech
BEAM_SIZE = 10  # Beam search width (increased for better accuracy)
BEST_OF = 10    # Number of candidates when sampling (increased for better results)
TEMPERATURE = 0.0  # Sampling temperature (0.0 = greedy/deterministic, best for accuracy)

# Whisper prompt to improve Spanish recognition
# This helps the model understand context and improve accuracy
INITIAL_PROMPT = "Hola, ¿cómo estás? Buenos días. Gracias. Por favor."  # Common Spanish phrases to guide the model

# Speaker identification (for future implementation)
SPEAKER_ID_ENABLED = False  # Enable speaker identification
SPEAKER_DB_PATH = "data/speakers.db"  # Path to speaker database
SPEAKER_MIN_CONFIDENCE = 0.75  # Minimum confidence to identify speaker

# Audio processing
SAMPLE_RATE = 16000  # Sample rate for Whisper (16kHz)
MAX_AUDIO_DURATION = 30.0  # Maximum audio duration in seconds
