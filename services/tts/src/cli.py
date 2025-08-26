from __future__ import annotations

"""Simple console utility to exercise the TTS engine.

This module allows sending text from the command line and playing the
resulting audio using the same pipeline as the microservice.  It is intended
for quick manual tests without running the HTTP server.
"""

import argparse
import io
import wave
from typing import Optional

from .engine import TTSEngine

try:  # Optional dependency used only when available
    import simpleaudio as sa  # type: ignore
except Exception:  # pragma: no cover - best effort fallback
    sa = None


class ConsoleTTS:
    """Helper class to synthesize and play speech from the console."""

    def __init__(self, engine: Optional[TTSEngine] = None) -> None:
        self.engine = engine or TTSEngine()

    def speak(self, text: str, emotion: str = "neutral") -> bytes:
        """Generate raw audio bytes for ``text`` with ``emotion``."""
        return self.engine.synthesize(text, emotion)

    def play(self, audio: bytes) -> None:
        """Attempt to play ``audio`` or write it to ``output.wav`` if playback fails."""
        if sa is not None:
            try:
                with wave.open(io.BytesIO(audio)) as wf:
                    obj = sa.WaveObject(
                        wf.readframes(wf.getnframes()),
                        wf.getnchannels(),
                        wf.getsampwidth(),
                        wf.getframerate(),
                    )
                obj.play().wait_done()
                return
            except Exception:  # pragma: no cover - playback failure
                pass
        # Fallback: write to file for manual inspection
        with open("output.wav", "wb") as f:
            f.write(audio)
        print("Audio written to output.wav")


def main() -> None:
    parser = argparse.ArgumentParser(description="TTS console test utility")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--emotion", default="neutral", help="Emotion preset to use")
    args = parser.parse_args()

    tts = ConsoleTTS()
    audio = tts.speak(args.text, args.emotion)
    tts.play(audio)


if __name__ == "__main__":  # pragma: no cover
    main()
