"""
Pytest configuration and shared fixtures for integration tests.
"""
import asyncio
import os
import sys
from typing import AsyncGenerator, Generator

import httpx
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def gateway_url() -> str:
    """Get Gateway service URL from environment."""
    return os.getenv("GATEWAY_HTTP", "http://127.0.0.1:8765")


@pytest.fixture(scope="session")
def conversation_url() -> str:
    """Get Conversation service URL from environment."""
    return os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")


@pytest.fixture(scope="session")
def tts_url() -> str:
    """Get TTS service URL from environment."""
    return os.getenv("TTS_HTTP", "http://127.0.0.1:8802")


@pytest.fixture(scope="session")
def assistant_url() -> str:
    """Get Assistant service URL from environment."""
    return os.getenv("ASSISTANT_HTTP", "http://127.0.0.1:8810")


@pytest.fixture(scope="session")
def ollama_url() -> str:
    """Get Ollama service URL from environment."""
    return os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


@pytest.fixture(scope="session")
def fish_url() -> str:
    """Get Fish Audio service URL from environment."""
    return os.getenv("FISH_TTS_HTTP", "http://127.0.0.1:8080/v1/tts")


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for testing."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def sample_emotions() -> list[str]:
    """List of valid emotion categories."""
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
def sample_text_spanish() -> list[str]:
    """Sample Spanish texts for testing."""
    return [
        "Hola, ¿cómo estás?",
        "Me siento muy feliz hoy.",
        "Estoy un poco triste.",
        "¡Qué sorpresa tan grande!",
        "No entiendo lo que está pasando.",
    ]


@pytest.fixture
def sample_text_english() -> list[str]:
    """Sample English texts for testing (if multilingual support added)."""
    return [
        "Hello, how are you?",
        "I feel very happy today.",
        "I'm a bit sad.",
        "What a big surprise!",
        "I don't understand what's happening.",
    ]


@pytest.fixture
async def check_service_health(http_client: httpx.AsyncClient):
    """
    Factory fixture to check if a service is healthy.

    Usage:
        is_healthy = await check_service_health("http://localhost:8801/health")
    """
    async def _check(url: str, timeout: float = 5.0) -> bool:
        try:
            response = await http_client.get(url, timeout=timeout)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    return _check


@pytest.fixture
def skip_if_service_unavailable():
    """
    Decorator to skip tests if required services are not available.

    Usage:
        @pytest.mark.requires_ollama
        async def test_something(skip_if_service_unavailable):
            await skip_if_service_unavailable("http://localhost:11434/health")
    """
    async def _skip(url: str, service_name: str = "Service"):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=3.0)
                if response.status_code != 200:
                    pytest.skip(f"{service_name} is not healthy")
            except (httpx.ConnectError, httpx.TimeoutException):
                pytest.skip(f"{service_name} is not running")

    return _skip
