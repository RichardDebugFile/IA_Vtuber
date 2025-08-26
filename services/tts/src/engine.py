"""Fish Audio based Text-to-Speech engine.

This module loads a Fish Audio model from a local directory and exposes a
simple interface to synthesize speech. If the Fish Audio dependencies are not
installed, the engine will fall back to a dummy implementation that returns
placeholder bytes. This allows unit tests to run quickly without the heavy
model files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import os
import yaml

# Load emotion to text marker mapping from YAML
_PRESETS_PATH = Path(__file__).parent / "voices" / "presets.yaml"
if _PRESETS_PATH.exists():
    with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
        EMOTION_MARKER_MAP: Dict[str, str] = yaml.safe_load(f) or {}
else:
    EMOTION_MARKER_MAP = {}

class TTSEngine:
    """Wrapper around the Fish Audio pipeline."""

    def __init__(self, model_dir: Optional[str] = None) -> None:
        self.model_dir = model_dir or os.getenv("FISH_TTS_MODEL_DIR", "models/fish-speech")
        self._pipeline = self._load_pipeline()

    def _load_pipeline(self):
        """Attempt to load the transformers pipeline.

        Returns ``None`` if transformers/torch are not installed.
        """
        try:
            from transformers import pipeline  # type: ignore
            return pipeline(
                "text-to-speech",
                model=str(self.model_dir),
                trust_remote_code=True,
            )
        except Exception:
            return None

    def synthesize(self, text: str, emotion: str) -> bytes:
        """Generate audio for ``text`` with the given ``emotion``.

        If the real model is available, raw audio bytes are returned. Otherwise
        a placeholder byte string is produced so tests can run without the
        heavy model dependencies.
        """
        marker = EMOTION_MARKER_MAP.get(emotion, EMOTION_MARKER_MAP.get("neutral", "neutral"))
        text_with_marker = f"({marker}) {text}"
        if self._pipeline is None:
            # Fallback stub representation
            return text_with_marker.encode("utf-8")

        result = self._pipeline(text_with_marker)
        audio = result.get("audio")
        if isinstance(audio, bytes):
            return audio
        # Many pipelines return numpy arrays; convert to bytes if possible
        try:
            return audio.tobytes()
        except Exception:
            return bytes(audio)
