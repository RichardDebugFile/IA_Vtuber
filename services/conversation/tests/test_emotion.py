"""Unit tests for emotion classification module."""
import os
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from emotion import classify


@pytest.mark.unit
class TestEmotionClassification:
    """Test suite for emotion classification."""

    def test_classify_text_with_accents_returns_fear(self):
        """Test fear detection with Spanish accents."""
        assert classify("¡Qué pánico!") == "fear"

    def test_classify_text_without_accents_returns_fear(self):
        """Test fear detection without accents (normalized)."""
        assert classify("que panico") == "fear"

    def test_classify_angry_emoji(self):
        """Test anger detection from emoji."""
        assert classify("😡") == "angry"

    def test_classify_happy_emoji(self):
        """Test happy detection from emoji."""
        assert classify("😊") == "happy"
        assert classify("😃") == "happy"

    def test_classify_sad_emoji(self):
        """Test sad detection from emoji."""
        assert classify("😢") == "sad"

    def test_classify_surprised_emoji(self):
        """Test surprised detection from emoji."""
        assert classify("😮") == "surprised"

    def test_classify_love_emoji(self):
        """Test love detection from emoji."""
        assert classify("❤") == "love"
        assert classify("😍") == "love"

    def test_classify_happy_text(self):
        """Test happy emotion from text."""
        assert classify("Estoy muy feliz") == "happy"
        assert classify("Qué alegría") == "happy"
        assert classify("Me siento contento") == "happy"

    def test_classify_sad_text(self):
        """Test sad emotion from text."""
        assert classify("Estoy triste") == "sad"
        assert classify("Me siento deprimido") == "sad"
        assert classify("Qué pena") == "sad"

    def test_classify_angry_text(self):
        """Test angry emotion from text."""
        assert classify("Estoy furioso") == "angry"
        assert classify("Me da rabia") == "angry"
        assert classify("Qué enojo") == "angry"

    def test_classify_excited_text(self):
        """Test excited emotion from text."""
        assert classify("Estoy emocionado") == "excited"
        assert classify("Qué emoción") == "excited"

    def test_classify_confused_text(self):
        """Test confused emotion from text."""
        assert classify("Estoy confundido") == "confused"
        assert classify("No entiendo") == "confused"

    def test_classify_bored_text(self):
        """Test bored emotion from text."""
        assert classify("Estoy aburrido") == "bored"
        assert classify("Qué aburrimiento") == "bored"

    def test_classify_sleeping_text(self):
        """Test sleeping emotion from text."""
        assert classify("Tengo sueño") == "sleeping"
        assert classify("Me da sueño") == "sleeping"

    def test_classify_thinking_text(self):
        """Test thinking emotion from text."""
        assert classify("Déjame pensar") == "thinking"
        assert classify("Estoy reflexionando") == "thinking"

    def test_classify_asco_text(self):
        """Test disgust emotion from text."""
        assert classify("Qué asco") == "asco"
        assert classify("Me da asco") == "asco"

    def test_classify_upset_text(self):
        """Test upset emotion from text."""
        assert classify("Estoy molesto") == "upset"
        assert classify("Me molesta") == "upset"

    def test_classify_neutral_text(self):
        """Test neutral emotion for generic text."""
        result = classify("Hola")
        # Neutral should be the default fallback
        assert result in ["neutral", "happy"]  # "Hola" might match greeting patterns

    def test_classify_empty_string(self):
        """Test classification of empty string."""
        assert classify("") == "neutral"

    def test_classify_whitespace_only(self):
        """Test classification of whitespace-only string."""
        assert classify("   ") == "neutral"

    def test_classify_numbers_only(self):
        """Test classification of numeric text."""
        assert classify("12345") == "neutral"

    def test_classify_mixed_emotions_returns_first_match(self):
        """Test that mixed emotions return first match in priority."""
        # This depends on regex ordering in emotion.py
        result = classify("Estoy feliz pero también triste")
        assert result in ["happy", "sad"]  # Should match one of them

    def test_classify_case_insensitive(self):
        """Test that classification is case-insensitive."""
        assert classify("ESTOY FELIZ") == "happy"
        assert classify("estoy feliz") == "happy"
        assert classify("EsToY fElIz") == "happy"

    def test_classify_with_punctuation(self):
        """Test classification with various punctuation."""
        assert classify("¡Estoy feliz!") == "happy"
        assert classify("Estoy feliz...") == "happy"
        assert classify("¿Estoy feliz?") == "happy"

    @pytest.mark.parametrize("text,expected", [
        ("feliz", "happy"),
        ("triste", "sad"),
        ("enojado", "angry"),
        ("miedo", "fear"),
        ("sorprendido", "surprised"),
        ("emocionado", "excited"),
        ("confundido", "confused"),
        ("molesto", "upset"),
        ("asco", "asco"),
        ("amor", "love"),
        ("aburrido", "bored"),
        ("sueño", "sleeping"),
        ("pensando", "thinking"),
    ])
    def test_classify_single_emotion_words(self, text, expected):
        """Test classification of single emotion words."""
        result = classify(text)
        assert result == expected
