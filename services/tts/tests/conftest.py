"""Pytest fixtures for TTS service tests."""
import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_emotions():
    """List of all valid emotions for TTS."""
    return [
        "neutral",
        "happy",
        "sad",
        "angry",
        "surprised",
        "excited",
        "confused",
        "upset",
        "fear",
        "asco",
        "love",
        "bored",
        "sleeping",
        "thinking",
    ]


@pytest.fixture
def sample_texts():
    """Sample texts for TTS synthesis."""
    return [
        "Hola, ¿cómo estás?",
        "Este es un texto de prueba.",
        "Me alegra verte de nuevo.",
        "¿Qué tal tu día?",
        "Hasta luego.",
    ]


@pytest.fixture
def short_text():
    """Short text for quick TTS tests."""
    return "Hola"


@pytest.fixture
def long_text():
    """Long text for TTS stress testing."""
    return (
        "Este es un texto muy largo que se utiliza para probar "
        "la capacidad del sistema de síntesis de voz para manejar "
        "entradas extensas. Contiene múltiples oraciones, con diferentes "
        "signos de puntuación. ¿Puede el sistema manejar preguntas? "
        "¡Y también exclamaciones! Además, incluye comas, puntos y "
        "otros elementos que podrían afectar la síntesis."
    )
