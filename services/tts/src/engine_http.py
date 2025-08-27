from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Union

import httpx
import ormsgpack
import yaml

# Cargar .env tanto en services/tts/.env como en la raíz del repo
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
except Exception:
    pass

# Cargar mapping de emociones
_PRESETS_PATH = Path(__file__).parent / "voices" / "presets.yaml"
if _PRESETS_PATH.exists():
    with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
        EMOTION_MARKER_MAP: Dict[str, str] = yaml.safe_load(f) or {}
else:
    EMOTION_MARKER_MAP = {}


class HTTPFishEngineError(Exception): ...
class HTTPFishServerUnavailable(HTTPFishEngineError): ...
class HTTPFishBadResponse(HTTPFishEngineError): ...


def _health_urls(tts_url: str) -> list[str]:
    base = tts_url
    for suffix in ("/v1/tts", "/tts"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return [f"{base}/v1/health", f"{base}/health"]


def _to_on_off(val: Union[str, bool, None], default: str = "on") -> str:
    if val is None:
        return default
    if isinstance(val, bool):
        return "on" if val else "off"
    v = str(val).strip().lower()
    if v in ("on", "off"):
        return v
    if v in ("1", "true", "yes", "y", "t"):
        return "on"
    if v in ("0", "false", "no", "n", "f"):
        return "off"
    return default


def _norm_path(p: Optional[str]) -> str:
    if not p:
        return ""
    s = str(p).strip()
    # quita comillas envolventes si vienen del .env
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s.strip()


class HTTPFishEngine:
    """
    Cliente para /v1/tts de fish-speech con referencia de voz.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_s: float = 600.0,
        *,
        ref_wav: Optional[str] = None,
        ref_text: Optional[str] = None,
        ref_id: Optional[str] = None,
        use_memory_cache: Optional[Union[str, bool]] = None,
    ) -> None:
        self.url = (base_url or os.getenv("FISH_TTS_HTTP") or "http://127.0.0.1:8080/v1/tts").rstrip("/")
        self.timeout = timeout_s

        # overrides / env
        self._ref_wav = _norm_path(ref_wav if ref_wav is not None else os.getenv("FISH_REF_WAV", ""))
        self._ref_text = os.getenv("FISH_REF_TXT", "") if ref_text is None else ref_text
        self._ref_id = os.getenv("FISH_REF_ID", "fixed-voice") if ref_id is None else ref_id
        self._use_cache = _to_on_off(
            use_memory_cache if use_memory_cache is not None else os.getenv("FISH_USE_MEMORY_CACHE", "on")
        )
        # 'list' (references=[{audio,text}]) o 'flat' (reference_audio/reference_text)
        self._ref_style = os.getenv("FISH_REF_PAYLOAD_STYLE", "list").strip().lower()

    def _build_reference(self) -> dict:
        ref_payload: dict = {}

        # cargar WAV
        audio_bytes: Optional[bytes] = None
        if self._ref_wav:
            p = Path(self._ref_wav)
            if not p.is_file():
                raise HTTPFishEngineError(
                    f"FISH_REF_WAV no existe o no es archivo: {self._ref_wav} "
                    f"(quita comillas en .env si las tiene y verifica la ruta)"
                )
            audio_bytes = p.read_bytes()

        # si no hay nada de referencia, retornamos vacío
        if not (audio_bytes or self._ref_text):
            return ref_payload

        cache_fields = {
            "memory_cache_id": self._ref_id,
            "use_memory_cache": self._use_cache,  # 'on'/'off'
        }

        if self._ref_style == "flat":
            if audio_bytes is not None:
                ref_payload["reference_audio"] = audio_bytes
            if self._ref_text:
                ref_payload["reference_text"] = self._ref_text
            ref_payload.update(cache_fields)
        else:
            # estilo recomendado (y el que tu server está validando)
            ref_item = {}
            if audio_bytes is not None:
                ref_item["audio"] = audio_bytes
            if self._ref_text:
                ref_item["text"] = self._ref_text
            # si falta audio, el server lo va a exigir → mejor avisar ahora
            if "audio" not in ref_item:
                raise HTTPFishEngineError(
                    "La referencia requiere 'audio'. Proporciona FISH_REF_WAV apuntando a un .wav válido."
                )
            ref_payload["references"] = [ref_item]
            ref_payload.update(cache_fields)

        return ref_payload

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
        # Prefijo de emoción
        marker = EMOTION_MARKER_MAP.get(emotion, EMOTION_MARKER_MAP.get("neutral", "neutral"))
        prefixed = text if text.lstrip().startswith("(") else f"({marker}) {text}"

        # Tu server espera 'text' (no 'input')
        payload = {"text": prefixed, "format": "wav"}
        # Añadir referencia/caché si hay
        payload.update(self._build_reference())

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
