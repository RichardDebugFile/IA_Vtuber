"""Configuration for STT service."""
import os
from typing import Literal

# Whisper model configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large-v3
DEVICE = os.getenv("DEVICE", "auto")  # auto, cpu, cuda
LANGUAGE = os.getenv("LANGUAGE", "es")  # es, en, auto
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float32")  # int8, float16, float32 (float32 for compatibility, float16 for GPU)

# Service configuration
STT_PORT = int(os.getenv("STT_PORT", "8806"))
HOST = os.getenv("STT_HOST", "127.0.0.1")

# VAD (Voice Activity Detection) configuration
VAD_CONFIG = {
    "threshold": 0.5,       # Threshold for voice detection (0.0-1.0)
    "min_silence_ms": 300,  # Minimum silence duration to split phrases (ms)
    "min_speech_ms": 250,   # Minimum valid speech duration (ms)
}

# Transcription settings
BEAM_SIZE = 5  # Beam search width (higher = more accurate but slower)
BEST_OF = 5    # Number of candidates when sampling (higher = more accurate)
TEMPERATURE = 0.0  # Sampling temperature (0.0 = greedy, >0.0 = more random)

# Speaker identification (for future implementation)
SPEAKER_ID_ENABLED = False  # Enable speaker identification
SPEAKER_DB_PATH = "data/speakers.db"  # Path to speaker database
SPEAKER_MIN_CONFIDENCE = 0.75  # Minimum confidence to identify speaker

# Audio processing
SAMPLE_RATE = 16000  # Sample rate for Whisper (16kHz)
MAX_AUDIO_DURATION = 30.0  # Maximum audio duration in seconds
