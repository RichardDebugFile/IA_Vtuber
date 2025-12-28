"""Pytest fixtures for Conversation service tests."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_happy_texts():
    """Sample texts that should classify as happy emotion."""
    return [
        "Estoy muy feliz",
        "Qué alegría verte",
        "Me siento genial",
        "😊",
        "Esto es maravilloso",
    ]


@pytest.fixture
def sample_sad_texts():
    """Sample texts that should classify as sad emotion."""
    return [
        "Estoy triste",
        "Me siento deprimido",
        "Qué pena",
        "😢",
        "Estoy melancólico",
    ]


@pytest.fixture
def sample_angry_texts():
    """Sample texts that should classify as angry emotion."""
    return [
        "Estoy furioso",
        "Me da rabia",
        "Qué enojo",
        "😡",
        "Estoy molesto",
    ]


@pytest.fixture
def sample_fear_texts():
    """Sample texts that should classify as fear emotion."""
    return [
        "Tengo miedo",
        "Qué pánico",
        "Me da terror",
        "Estoy asustado",
        "Qué susto",
    ]


@pytest.fixture
def sample_neutral_texts():
    """Sample texts that should classify as neutral emotion."""
    return [
        "Hola",
        "¿Cómo estás?",
        "El cielo es azul",
        "Son las tres",
        "Información general",
    ]
