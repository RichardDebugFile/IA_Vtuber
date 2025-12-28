# services/tts/src/voices/__init__.py
"""Voice presets and emotion marker configuration."""

from .presets import get_emotion_marker_map, get_emotion_marker

__all__ = ["get_emotion_marker_map", "get_emotion_marker"]
