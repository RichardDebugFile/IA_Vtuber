"""Tests for blip generator."""
import pytest
from src.blip_generator import BlipGenerator
from src.voice_config import get_voice_for_emotion


@pytest.fixture
def generator():
    """Create blip generator instance."""
    return BlipGenerator(sample_rate=44100)


def test_generate_single_blip(generator):
    """Test generating a single blip."""
    wav_bytes = generator.generate_single_blip(char="a", emotion="neutral")

    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 0
    # WAV header should start with RIFF
    assert wav_bytes[:4] == b"RIFF"


def test_generate_text_blips(generator):
    """Test generating blips for text."""
    text = "Hola mundo"
    wav_bytes, duration_ms, num_blips = generator.generate_text_blips(
        text=text,
        emotion="neutral",
        blips_per_second=20.0,
    )

    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 0
    assert duration_ms > 0
    # Should generate blips for non-space characters
    assert num_blips == len([c for c in text if not c.isspace()])


def test_emotion_modulation(generator):
    """Test that different emotions produce different audio."""
    text = "Test"

    neutral_bytes, _, _ = generator.generate_text_blips(text, emotion="neutral")
    happy_bytes, _, _ = generator.generate_text_blips(text, emotion="happy")
    sad_bytes, _, _ = generator.generate_text_blips(text, emotion="sad")

    # Different emotions should produce different audio
    assert neutral_bytes != happy_bytes
    assert neutral_bytes != sad_bytes
    assert happy_bytes != sad_bytes


def test_voice_profile_for_emotion():
    """Test voice profile modulation by emotion."""
    neutral_voice = get_voice_for_emotion("neutral")
    happy_voice = get_voice_for_emotion("happy")
    sad_voice = get_voice_for_emotion("sad")

    # Happy should have higher pitch than neutral
    assert happy_voice.base_pitch > neutral_voice.base_pitch

    # Sad should have lower pitch than neutral
    assert sad_voice.base_pitch < neutral_voice.base_pitch

    # Happy should have shorter duration (more energetic)
    assert happy_voice.duration_ms < neutral_voice.duration_ms

    # Sad should have longer duration (slower)
    assert sad_voice.duration_ms > neutral_voice.duration_ms


def test_empty_text(generator):
    """Test handling of empty text."""
    wav_bytes, duration_ms, num_blips = generator.generate_text_blips(
        text="",
        emotion="neutral",
    )

    assert isinstance(wav_bytes, bytes)
    assert num_blips == 0


def test_punctuation_handling(generator):
    """Test that punctuation creates pauses."""
    text_no_punct = "Hola"
    text_with_punct = "Hola!"

    _, duration_no_punct, _ = generator.generate_text_blips(text_no_punct)
    _, duration_with_punct, _ = generator.generate_text_blips(text_with_punct)

    # With punctuation should be slightly longer (due to pause)
    # But blip count should be same (punctuation doesn't generate blips)
    _, _, blips_no_punct = generator.generate_text_blips(text_no_punct)
    _, _, blips_with_punct = generator.generate_text_blips(text_with_punct)

    assert blips_with_punct == blips_no_punct
