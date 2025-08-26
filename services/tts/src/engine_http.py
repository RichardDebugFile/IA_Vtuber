from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict

import httpx
import ormsgpack
import yaml

try:
    from dotenv import load_dotenv, find_dotenv
    # 1) intenta en services/tts/.env (compatibilidad previa)
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
    # 2) y también busca hacia arriba (soporta IA_Vtuber/.env)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
except Exception:
    pass



# Cargamos el mapping de emociones desde voices/presets.yaml
_PRESETS_PATH = Path(__file__).parent / "voices" / "presets.yaml"
if _PRESETS_PATH.exists():
    with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
        EMOTION_MARKER_MAP: Dict[str, str] = yaml.safe_load(f) or {}
else:
    EMOTION_MARKER_MAP = {}


class HTTPFishEngineError(Exception):
    ...


class HTTPFishServerUnavailable(HTTPFishEngineError):
    ...


class HTTPFishBadResponse(HTTPFishEngineError):
    ...


def _health_urls(tts_url: str) -> list[str]:
    # De "http://.../v1/tts" me quedo con la base para chequear /health
    base = tts_url
    for suffix in ("/v1/tts", "/tts"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return [f"{base}/v1/health", f"{base}/health"]


class HTTPFishEngine:
    """
    Cliente minimal para el endpoint /v1/tts del server fish-speech.
    Envía MessagePack: {"text": "(emotion) texto", "format": "wav"}.
    """

    def __init__(self, base_url: Optional[str] = None, timeout_s: float = 600.0) -> None:
        self.url = (base_url or os.getenv("FISH_TTS_HTTP") or "http://127.0.0.1:8080/v1/tts").rstrip("/")
        self.timeout = timeout_s

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as c:
                for u in _health_urls(self.url):
                    r = c.get(u)
                    if r.status_code == 200:
                        try:
                            j = r.json()
                        except Exception:
                            j = {}
                        if j.get("status") == "ok" or j.get("ok") is True:
                            return True
        except Exception:
            return False
        return False

    def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        # Prefijo de emoción: si ya viene "(...)" no lo duplicamos
        marker = EMOTION_MARKER_MAP.get(emotion, EMOTION_MARKER_MAP.get("neutral", "neutral"))
        prefixed = text if text.lstrip().startswith("(") else f"({marker}) {text}"

        payload = {"text": prefixed, "format": "wav"}
        headers = {"Content-Type": "application/msgpack"}

        try:
            r = httpx.post(self.url, content=ormsgpack.packb(payload), headers=headers, timeout=self.timeout)
        except httpx.RequestError as e:
            raise HTTPFishServerUnavailable(f"No pude contactar el server {self.url}: {e}") from e

        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise HTTPFishBadResponse(f"HTTP {r.status_code} en {self.url}. Detalle: {detail}")

        if not r.content:
            raise HTTPFishBadResponse("Respuesta vacía del server TTS")
        return r.content
