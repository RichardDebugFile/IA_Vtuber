# services/tts/src/voices/presets.py
"""Load and access emotion marker mappings from presets.yaml."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

_EMOTION_MARKER_MAP: Dict[str, str] | None = None

def get_emotion_marker_map() -> Dict[str, str]:
    """Get the emotion to Fish Audio marker mapping.

    Returns:
        Dictionary mapping emotion names to Fish Audio markers

    Raises:
        FileNotFoundError: If presets.yaml not found
        ImportError: If PyYAML not installed
    """
    global _EMOTION_MARKER_MAP

    if _EMOTION_MARKER_MAP is not None:
        return _EMOTION_MARKER_MAP

    if yaml is None:
        raise ImportError("PyYAML not installed. Install with: pip install pyyaml")

    # Find presets.yaml relative to this file
    presets_path = Path(__file__).parent / "presets.yaml"

    if not presets_path.exists():
        raise FileNotFoundError(f"presets.yaml not found at {presets_path}")

    with open(presets_path, "r", encoding="utf-8") as f:
        _EMOTION_MARKER_MAP = yaml.safe_load(f)

    return _EMOTION_MARKER_MAP

def get_emotion_marker(emotion: str, default: str = "neutral") -> str:
    """Get the Fish Audio marker for an emotion.

    Args:
        emotion: Emotion name (e.g., "happy", "sad")
        default: Default marker if emotion not found

    Returns:
        Fish Audio marker string (e.g., "joyful", "sad")
    """
    emotion_map = get_emotion_marker_map()
    return emotion_map.get(emotion, emotion_map.get(default, default))
