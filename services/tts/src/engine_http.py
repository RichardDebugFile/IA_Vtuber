from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Union

import httpx
import ormsgpack
import yaml
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from logging_config import logger

# Cargar .env tanto en services/tts/.env como en la raíz del repo
# IMPORTANTE: override=True para que el .env tenga prioridad sobre variables del sistema
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=True)
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
        timeout_s: float = 60.0,
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
        """Check if Fish Audio server is healthy."""
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
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        after=after_log(logger, "INFO")
    )
    def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """Synthesize speech using Fish Audio API with automatic retries.

        Args:
            text: Text to synthesize
            emotion: Emotion marker (default: neutral) - DEPRECATED with voice cloning

        Returns:
            WAV audio bytes

        Raises:
            HTTPFishServerUnavailable: If server is unreachable (after retries)
            HTTPFishBadResponse: If server returns error or invalid data
        """
        # IMPORTANTE: Fish Speech 1.5 con clonación de voz NO usa tags de emoción textual
        # El control emocional se hace mediante la referencia de audio
        # Añadir tags como "(joyful)" hace que el modelo los lea literalmente
        # Por lo tanto, usamos el texto sin modificar
        final_text = text

        logger.debug(
            "Synthesizing audio",
            text_length=len(text),
            emotion=emotion,
            using_emotion_tags=False,  # Deshabilitado para clonación de voz
            url=self.url
        )

        # Calcular word count para optimización de parámetros
        word_count = len(text.split())

        # Optimización de parámetros según longitud de texto
        # Para textos cortos (modo streamer): parámetros optimizados para velocidad
        # Para textos largos (modo youtuber): parámetros balanceados
        # Basado en análisis de Fish Speech upstream y benchmarks de rendimiento
        if word_count <= 20:
            # Modo streamer: optimizado para baja latencia (<4s para 10 palabras)
            chunk_length = 150          # Óptimo para textos cortos
            max_new_tokens = 512        # Reducido de 1024 para evitar generación excesiva
            temperature = 0.65          # Reducido de 0.7 para mayor consistencia y velocidad
            top_p = 0.7                 # Mantener exploración controlada
        else:
            # Modo youtuber: balanceado calidad/velocidad
            chunk_length = 200          # Chunks más grandes para mejor contexto
            max_new_tokens = 768        # Reducido de 1024 para mejor rendimiento
            temperature = 0.7           # Reducido de 0.8 para menor variabilidad
            top_p = 0.7                 # Unificado con modo streamer

        # Tu server espera 'text' (no 'input')
        payload = {
            "text": final_text,  # Sin tags de emoción - Fish 1.5 usa clonación de voz
            "format": "wav",
            "chunk_length": chunk_length,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": 1.25,  # Incrementado de 1.1 para reducir bucles de generación
        }
        # Añadir referencia/caché si hay
        payload.update(self._build_reference())

        headers = {"Content-Type": "application/msgpack"}

        try:
            r = httpx.post(self.url, content=ormsgpack.packb(payload), headers=headers, timeout=self.timeout)
        except httpx.RequestError as e:
            logger.error(f"Fish Audio request error: {e}", url=self.url)
            raise HTTPFishServerUnavailable(f"No pude contactar el server {self.url}: {e}") from e
        except httpx.TimeoutException as e:
            logger.error(f"Fish Audio timeout: {e}", url=self.url, timeout=self.timeout)
            raise HTTPFishServerUnavailable(f"Timeout al contactar {self.url} ({self.timeout}s): {e}") from e

        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:200]  # Limit detail length

            logger.error(
                "Fish Audio HTTP error",
                status_code=r.status_code,
                detail=detail,
                url=self.url
            )
            raise HTTPFishBadResponse(f"HTTP {r.status_code} en {self.url}. Detalle: {detail}")

        if not r.content:
            logger.error("Fish Audio returned empty response", url=self.url)
            raise HTTPFishBadResponse("Respuesta vacía del server TTS")

        logger.debug(f"Synthesis successful", audio_size=len(r.content))
        return r.content
