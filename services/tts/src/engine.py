"""DEPRECATED: Local TTS Engine (Stub for Testing Only).

WARNING: This module is DEPRECATED and does NOT work with Fish Audio models.
The transformers pipeline approach is incompatible with Fish Audio's architecture.

ONLY USE FOR TESTING: This stub returns text encoded as bytes for unit tests.
For production, use engine_http.HTTPFishEngine with a running Fish Audio server.

This module is kept only for backward compatibility with existing tests.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import os
import yaml
import warnings

# Load emotion to text marker mapping from YAML
_PRESETS_PATH = Path(__file__).parent / "voices" / "presets.yaml"
if _PRESETS_PATH.exists():
    with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
        EMOTION_MARKER_MAP: Dict[str, str] = yaml.safe_load(f) or {}
else:
    EMOTION_MARKER_MAP = {}


class TTSEngine:
    """DEPRECATED: Stub TTS engine for testing only.

    WARNING: This class does NOT produce real audio. It only returns text
    encoded as UTF-8 bytes for use in unit tests.

    For real TTS synthesis, use HTTPFishEngine with a running Fish Audio server.
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        """Initialize stub engine.

        Args:
            model_dir: Ignored. Kept for backward compatibility.
        """
        warnings.warn(
            "TTSEngine is DEPRECATED and does not produce real audio. "
            "Use HTTPFishEngine for production TTS synthesis.",
            DeprecationWarning,
            stacklevel=2
        )
        self.model_dir = model_dir or os.getenv("FISH_TTS_MODEL_DIR", "models/fish-speech")

    def synthesize(self, text: str, emotion: str) -> bytes:
        """Return text encoded as bytes (STUB for testing).

        WARNING: This does NOT generate real audio. Returns UTF-8 encoded text.

        Args:
            text: Input text
            emotion: Emotion label (used to add marker prefix)

        Returns:
            UTF-8 encoded text with emotion marker (NOT real audio)
        """
        marker = EMOTION_MARKER_MAP.get(emotion, EMOTION_MARKER_MAP.get("neutral", "neutral"))
        text_with_marker = f"({marker}) {text}"
        # Return text as bytes (stub for testing)
        return text_with_marker.encode("utf-8")
