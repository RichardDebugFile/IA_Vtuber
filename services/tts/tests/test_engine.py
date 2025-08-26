import os
import sys
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.engine import TTSEngine, EMOTION_MARKER_MAP

engine = TTSEngine()

@pytest.mark.parametrize("emotion", sorted(EMOTION_MARKER_MAP.keys()))
def test_synthesize_returns_bytes(emotion):
    audio = engine.synthesize("hola", emotion)
    assert isinstance(audio, bytes)
    assert audio.startswith(f"({EMOTION_MARKER_MAP.get(emotion)}) ".encode())
