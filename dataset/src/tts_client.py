"""TTS Service client for audio synthesis."""

import httpx
import base64
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TTSClient:
    """Client for communicating with TTS and Fish Speech services."""

    def __init__(self, base_url: str = "http://127.0.0.1:8802"):
        """
        Initialize TTS client.

        Args:
            base_url: Base URL of the TTS service
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)  # Increased for longer phrases

    async def check_health(self) -> bool:
        """
        Check if TTS service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"TTS health check failed: {e}")
            return False

    async def get_available_emotions(self) -> Optional[list]:
        """
        Get list of available emotions from TTS service.

        Returns:
            List of emotion names or None if request fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/emotions")
            if response.status_code == 200:
                data = response.json()
                return data.get("emotions", [])
            return None
        except Exception as e:
            logger.warning(f"Failed to get emotions: {e}")
            return None

    def _detect_emotion_from_text(self, text: str) -> str:
        """
        Detect emotion from text content based on keywords and punctuation.

        Args:
            text: Text to analyze

        Returns:
            Detected emotion (neutral, happy, sad, angry, surprised, etc.)
        """
        text_lower = text.lower()

        # Happy indicators
        happy_keywords = ['feliz', 'contenta', 'alegría', 'genial', 'excelente', 'fantástico',
                         'maravilla', 'increíble', 'me encanta', 'perfecto', 'bien hecho']
        if any(kw in text_lower for kw in happy_keywords):
            return "happy"

        # Sad indicators
        sad_keywords = ['triste', 'decepcionada', 'terrible', 'horrible', 'lamento']
        if any(kw in text_lower for kw in sad_keywords):
            return "sad"

        # Angry indicators
        angry_keywords = ['molesta', 'enfadada', 'disgusta', 'odio']
        if any(kw in text_lower for kw in angry_keywords):
            return "angry"

        # Surprised indicators
        surprised_keywords = ['sorpresa', 'no puedo creer', 'inesperado', 'wow']
        if any(kw in text_lower for kw in surprised_keywords) or text.count('!') >= 2:
            return "surprised"

        # Fearful indicators
        fearful_keywords = ['miedo', 'nerviosa', 'preocupada', 'horror']
        if any(kw in text_lower for kw in fearful_keywords):
            return "fearful"

        # Contemplative indicators (questions, thinking)
        if text.count('?') >= 2 or 'déjame pensar' in text_lower or 'hmm' in text_lower:
            return "contemplative"

        # Default to neutral
        return "neutral"

    async def synthesize(
        self,
        text: str,
        backend: str = "http",
        emotion: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Generate audio from text using TTS service.

        Emotion is auto-detected from text content if not provided.

        Args:
            text: Text to synthesize
            backend: Backend to use ("http" or "docker")
            emotion: Optional emotion override (auto-detected if None)

        Returns:
            Audio data as bytes or None if synthesis fails
        """
        # Auto-detect emotion from text if not provided
        was_auto_detected = emotion is None
        if emotion is None:
            emotion = self._detect_emotion_from_text(text)

        try:
            logger.info(f"Synthesizing: '{text[:50]}...' with emotion '{emotion}' (auto-detected: {was_auto_detected})")

            response = await self.client.post(
                f"{self.base_url}/synthesize",
                json={
                    "text": text,
                    "emotion": emotion,
                    "backend": backend
                },
                timeout=120.0  # Increased for longer phrases (up to 19 words)
            )

            if response.status_code == 200:
                data = response.json()
                audio_b64 = data.get("audio_b64")

                if not audio_b64:
                    logger.error("No audio_b64 in response")
                    return None

                # Decode base64 to bytes
                audio_bytes = base64.b64decode(audio_b64)
                logger.info(f"Synthesis successful: {len(audio_bytes)} bytes")
                return audio_bytes

            else:
                logger.error(f"Synthesis failed: HTTP {response.status_code} - {response.text}")
                return None

        except httpx.TimeoutException:
            logger.error(f"Synthesis timeout for text: '{text[:50]}...'")
            return None
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
