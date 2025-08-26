# services/voice/src/tts/fish_client.py
from __future__ import annotations
import base64
import io
import json
import logging
from typing import Optional, Tuple

import numpy as np
import requests
import soundfile as sf

from ..config import SETTINGS

log = logging.getLogger("fish_client")

# memo en proceso para no redescubrir siempre
_DISCOVERED_PATH: Optional[str] = None

# Algunas rutas típicas vistas en forks de Fish / OpenAudio
_CANDIDATE_PATHS = [
    "/v1/tts",      
    "/tts",
    "/api/tts",
    "/api/tts/generate",
    "/speak",
    "/generate",
]

# Distintos “shapes” de payload que he visto
def _payload_variants(text: str, emotion: Optional[str], lang: Optional[str], sr: int):
    e = emotion or ""
    l = (lang or SETTINGS.fish_lang or "es").lower()
    return [
        # 1) Lo más común en OpenAudio: text/lang/emotion y sample_rate
        {"text": text, "lang": l, "emotion": e, "sample_rate": sr},
        # 2) Text + language
        {"text": text, "language": l, "emotion": e, "sample_rate": sr},
        # 3) prompt
        {"prompt": text, "language": l, "sample_rate": sr},
        # 4) input
        {"input": text, "lang": l, "sample_rate": sr},
        # 5) súper mínimo
        {"text": text},
    ]


def _discover_tts_path(base: str) -> str:
    # 1) OpenAPI…
    try:
        r = requests.get(base.rstrip("/") + "/openapi.json", timeout=5)
        if r.ok:
            data = r.json()
            paths = data.get("paths", {})
            for path, spec in paths.items():
                post = spec.get("post")
                if not post:
                    continue
                s = json.dumps(post).lower()
                if "tts" in path.lower() or '"text"' in s:
                    log.info("[fish] descubierto por openapi.json -> %s", path)
                    return path
    except Exception as ex:
        log.debug("[fish] openapi.json no disponible: %s", ex)

    # 2) Candidatos
    for p in _CANDIDATE_PATHS:
        url = base.rstrip("/") + p
        try:
            rr = requests.options(url, timeout=3)
            # OPTIONS correcto suele ser 200/204 (algunas APIs devuelven 405 si no permiten OPTIONS)
            if rr.status_code in (200, 204):
                log.info("[fish] candidato OPTIONS OK -> %s (status=%s)", p, rr.status_code)
                return p
        except Exception:
            pass
        try:
            rr = requests.head(url, timeout=3)
            # HEAD: aceptamos 200 (existe) o 405 (método no permitido, pero ruta existe)
            if rr.status_code in (200, 405):
                log.info("[fish] candidato HEAD OK -> %s (status=%s)", p, rr.status_code)
                return p
        except Exception:
            pass

    raise RuntimeError(
        f"No se encontró endpoint TTS en {base}. Abre {base}/ y verifica manualmente; "
        f"o fija FISH_TTS_PATH en .env."
    )



def _decode_audio_response(r: requests.Response) -> Tuple[np.ndarray, int]:
    """
    Acepta:
      - audio/wav binario
      - JSON con 'wav' (base64) o 'audio' (base64) o 'samples' + 'sample_rate'
    """
    ctype = (r.headers.get("content-type") or "").lower()
    raw = r.content

    if "audio" in ctype or raw.startswith(b"RIFF"):
        y, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if y.ndim == 2:  # mezcla a mono si viene estéreo
            y = y.mean(axis=1)
        return y.astype(np.float32), int(sr)

    # JSON
    data = r.json()
    if "samples" in data and "sample_rate" in data:
        y = np.array(data["samples"], dtype=np.float32)
        return y, int(data["sample_rate"])
    for key in ("wav", "audio", "audio_base64", "wav_base64"):
        b64 = data.get(key)
        if b64:
            pcm = base64.b64decode(b64)
            y, sr = sf.read(io.BytesIO(pcm), dtype="float32", always_2d=False)
            if y.ndim == 2:
                y = y.mean(axis=1)
            return y.astype(np.float32), int(sr)

    raise RuntimeError(f"Respuesta TTS desconocida (ctype={ctype}): {data!r}")


def synthesize(text: str, emotion: Optional[str], style: Optional[str], sr: int) -> Tuple[np.ndarray, int]:
    base = SETTINGS.fish_base.rstrip("/")
    global _DISCOVERED_PATH

    path = SETTINGS.fish_tts_path or _DISCOVERED_PATH or _discover_tts_path(base)
    url = base + path
    headers = {"accept": "application/json", "content-type": "application/json"}

    last_err: Optional[Exception] = None
    for payload in _payload_variants(text, emotion, SETTINGS.fish_lang, sr):
        try:
            log.debug("[fish] POST %s payload=%s", url, {**payload, "text": payload.get("text","")[:40]+"..."})
            # connect=5s, read = SETTINGS.fish_timeout (p.ej. 120s)
            r = requests.post(url, headers=headers, json=payload, timeout=(5, SETTINGS.fish_timeout))
            if r.status_code == 404:
                log.warning("[fish] 404 en %s, reintentando autodescubrimiento…", url)
                _DISCOVERED_PATH = None
                path = _discover_tts_path(base)
                url = base + path
                continue
            r.raise_for_status()
            return _decode_audio_response(r)
        except Exception as ex:
            last_err = ex

    raise RuntimeError(
        f"Fish TTS falló en {url}. Último error: {last_err}. "
        f"Prueba fijando FISH_TTS_PATH en .env y reinicia."
    )

