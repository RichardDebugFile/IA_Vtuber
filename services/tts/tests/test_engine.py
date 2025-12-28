"""Unit tests for TTS engine module."""
import os
import sys
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.engine import TTSEngine, EMOTION_MARKER_MAP


@pytest.fixture
def engine():
    """Create a TTS engine instance for testing."""
    return TTSEngine()


@pytest.mark.unit
@pytest.mark.parametrize("emotion", sorted(EMOTION_MARKER_MAP.keys()))
def test_synthesize_returns_bytes(engine, emotion):
    """Test that synthesize returns bytes for all emotions."""
    audio = engine.synthesize("hola", emotion)
    assert isinstance(audio, bytes)
    assert audio.startswith(f"({EMOTION_MARKER_MAP.get(emotion)}) ".encode())


@pytest.mark.unit
def test_synthesize_with_empty_text(engine):
    """Test synthesize with empty text."""
    audio = engine.synthesize("", "neutral")
    assert isinstance(audio, bytes)


@pytest.mark.unit
def test_synthesize_with_long_text(engine):
    """Test synthesize with long text."""
    long_text = "palabra " * 100
    audio = engine.synthesize(long_text, "neutral")
    assert isinstance(audio, bytes)
    assert len(audio) > 0


@pytest.mark.unit
def test_synthesize_with_special_characters(engine):
    """Test synthesize with special characters."""
    special_text = "¿Hola! ¿Cómo estás? ñ á é í ó ú"
    audio = engine.synthesize(special_text, "neutral")
    assert isinstance(audio, bytes)


@pytest.mark.unit
def test_synthesize_with_numbers(engine):
    """Test synthesize with numbers."""
    audio = engine.synthesize("123 456 789", "neutral")
    assert isinstance(audio, bytes)


@pytest.mark.unit
def test_synthesize_with_invalid_emotion_uses_default(engine):
    """Test that invalid emotion falls back to default."""
    audio = engine.synthesize("hola", "invalid_emotion")
    assert isinstance(audio, bytes)


@pytest.mark.unit
def test_emotion_marker_map_completeness():
    """Test that all expected emotions have markers."""
    expected_emotions = {
        "neutral", "happy", "sad", "angry", "surprised",
        "excited", "confused", "upset", "fear", "asco",
        "love", "bored", "sleeping", "thinking"
    }

    for emotion in expected_emotions:
        assert emotion in EMOTION_MARKER_MAP
        assert isinstance(EMOTION_MARKER_MAP[emotion], str)
        assert len(EMOTION_MARKER_MAP[emotion]) > 0


@pytest.mark.unit
def test_synthesize_consistent_output(engine):
    """Test that same input produces consistent output."""
    text = "Texto de prueba"
    emotion = "neutral"

    audio1 = engine.synthesize(text, emotion)
    audio2 = engine.synthesize(text, emotion)

    # In mock mode, output should be identical
    assert audio1 == audio2
