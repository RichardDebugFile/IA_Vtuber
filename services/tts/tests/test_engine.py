import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sys as _sys
_sys.modules.pop("src.engine", None)
_sys.modules.pop("src", None)
from src.engine import TTSEngine, EMOTION_MARKER_MAP

engine = TTSEngine()

@pytest.mark.parametrize("emotion", sorted(EMOTION_MARKER_MAP.keys()))
def test_synthesize_returns_bytes(emotion):
    audio = engine.synthesize("hola", emotion)
    assert isinstance(audio, bytes)
    assert audio.startswith(f"({EMOTION_MARKER_MAP.get(emotion)}) ".encode())
