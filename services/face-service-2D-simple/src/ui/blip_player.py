"""Blip audio player - reproduce sonidos sincronizados con texto letra por letra."""
import os
import threading
from typing import Optional
import httpx


class BlipPlayer:
    """Reproduce blips (sonidos de diálogo) sincronizados con texto."""

    def __init__(self, blips_service_url: str = "http://127.0.0.1:8804"):
        self.blips_url = blips_service_url
        self.current_audio = None
        self.is_playing = False

    def play_for_text(self, text: str, emotion: str = "neutral") -> bool:
        """Request and play blips audio for given text.

        Args:
            text: El texto completo que se mostrará
            emotion: La emoción actual (neutral, happy, sad, etc.)

        Returns:
            True si se inició la reproducción, False si falló
        """
        if not text or not text.strip():
            return False

        # Request blips audio from service
        def _play_async():
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.post(
                        f"{self.blips_url}/blips/generate",
                        json={
                            "text": text,
                            "emotion": emotion,
                            "speed": 20.0,  # characters per second
                            "volume": 0.7
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        audio_b64 = data.get("audio_b64", "")
                        if audio_b64:
                            # Audio received - in a real implementation we'd play it
                            # For now, we just mark that it's playing
                            self.is_playing = True
                            # TODO: Implement actual audio playback with PySide6/Qt
                            pass
            except Exception as e:
                print(f"[BLIP_PLAYER] Error requesting blips: {e}")
                self.is_playing = False

        # Start async request
        thread = threading.Thread(target=_play_async, daemon=True)
        thread.start()
        return True

    def stop(self):
        """Stop current blip playback."""
        self.is_playing = False
        # TODO: Stop actual audio playback
