import os, yaml

def load_emotions_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def apply_emotion_tags(text: str, emotion: str | None, style: str | None, mapping: dict) -> str:
    parts = []
    if emotion:
        tag = (mapping.get(emotion) or "").strip()
        if tag:
            parts.append(tag)
    if style:
        parts.append(style.strip())
    if parts:
        return " ".join(parts) + " " + (text or "")
    return text or ""
