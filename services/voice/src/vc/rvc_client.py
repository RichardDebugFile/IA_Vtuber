# services/voice/src/vc/rvc_client.py
from __future__ import annotations
import io, os, json, tempfile
from typing import Tuple, Optional, List

import numpy as np
import soundfile as sf
import requests

from ..config import SETTINGS


# ----------------------
# Utilidades comunes
# ----------------------
def _resample_if_needed(y: np.ndarray, sr: int, target_sr: int) -> tuple[np.ndarray, int]:
    if sr == target_sr:
        return y.astype(np.float32), sr
    # Interpolación lineal (suficiente para VC). Si tienes librosa/torchaudio, puedes cambiarlo.
    import math
    n = int(math.ceil(len(y) * target_sr / sr))
    if n <= 1:
        return y.astype(np.float32), sr
    x_old = np.linspace(0.0, 1.0, len(y), endpoint=False)
    x_new = np.linspace(0.0, 1.0, n, endpoint=False)
    y_new = np.interp(x_new, x_old, y).astype(np.float32)
    return y_new, target_sr


def _decode_audio_response(resp: requests.Response) -> Tuple[np.ndarray, int]:
    """
    Acepta:
      - audio/* binario (WAV/PCM)
      - JSON con 'wav'/'audio' base64
      - JSON con 'samples' + 'sample_rate'
    """
    ctype = (resp.headers.get("content-type") or "").lower()
    raw = resp.content

    # 1) Respuesta binaria de audio
    if "audio" in ctype or raw[:4] == b"RIFF":
        y, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if getattr(y, "ndim", 1) == 2:
            y = y.mean(axis=1)
        return y.astype(np.float32), int(sr)

    # 2) Respuesta JSON
    data = resp.json()
    if "samples" in data and "sample_rate" in data:
        y = np.array(data["samples"], dtype=np.float32)
        return y, int(data["sample_rate"])

    for k in ("wav", "audio", "audio_base64", "wav_base64"):
        b64 = data.get(k)
        if b64:
            import base64
            pcm = base64.b64decode(b64)
            y, sr = sf.read(io.BytesIO(pcm), dtype="float32", always_2d=False)
            if getattr(y, "ndim", 1) == 2:
                y = y.mean(axis=1)
            return y.astype(np.float32), int(sr)

    raise RuntimeError(f"Respuesta RVC desconocida (ctype={ctype}): {data!r}")


# ----------------------
# MODO: device (VB-Audio)
# ----------------------
def _convert_via_devices(y: np.ndarray, sr: int) -> Tuple[np.ndarray, int]:
    """
    Reproduce el TTS hacia el dispositivo "play" (Cable A) y graba loopback del "tap" (Cable B),
    con w-Okada GUI en medio realizando la conversión.

    Variables de entorno (defaults):
      RVC_PLAY_TO = "CABLE Input (VB-Audio Virtual Cable)"          # adonde reproducimos
      RVC_TAP_FROM = "CABLE B Input (VB-Audio Virtual Cable B)"     # de donde grabamos (loopback)
      RVC_SR = 48000
      RVC_PAD_MS = 180
    """
    import soundcard as sc  # pip install soundcard

    play_name = os.getenv("RVC_PLAY_TO", "CABLE Input (VB-Audio Virtual Cable)")
    tap_name  = os.getenv("RVC_TAP_FROM", "CABLE B Input (VB-Audio Virtual Cable B)")
    target_sr = int(os.getenv("RVC_SR", "48000"))
    pad_ms    = int(os.getenv("RVC_PAD_MS", "180"))

    y48, sr48 = _resample_if_needed(y.astype(np.float32), sr, target_sr)

    # Buscar speaker de reproducción exacto
    speaker_play = None
    for spk in sc.all_speakers():
        if spk.name == play_name:
            speaker_play = spk
            break
    if speaker_play is None:
        names = [s.name for s in sc.all_speakers()]
        raise RuntimeError(f"No se encontró speaker de reproducción: '{play_name}'. Disponibles: {names}")

    # Loopback: usar el mismo concepto de "speaker" como mic con include_loopback
    mic_loop = sc.get_microphone(tap_name, include_loopback=True)
    if mic_loop is None:
        names = [s.name for s in sc.all_speakers()]
        raise RuntimeError(f"No se encontró speaker de tap/loopback: '{tap_name}'. Disponibles: {names}")

    # Duración a grabar = duración señal + margen
    dur_s = len(y48) / float(sr48)
    total_s = dur_s + (pad_ms / 1000.0)
    frames_to_record = int(total_s * sr48)

    rec = None
    recorded = None
    try:
        rec = mic_loop.recorder(samplerate=sr48)
        rec.__enter__()
        _ = rec.record(int(0.05 * sr48))  # preroll

        with speaker_play.player(samplerate=sr48) as player:
            player.play(y48)                      # reproducir TTS hacia w-Okada
            recorded = rec.record(frames_to_record)

        post = rec.record(int(0.05 * sr48))      # postroll
        recorded = np.concatenate([recorded, post], axis=0)
    finally:
        if rec is not None:
            rec.__exit__(None, None, None)

    # Mono
    if recorded.ndim == 2:
        recorded = recorded.mean(axis=1).astype(np.float32)

    # Recorte simple de silencios extremos
    thr = 1e-4
    nz = np.flatnonzero(np.abs(recorded) > thr)
    if nz.size >= 2:
        recorded = recorded[nz[0]: nz[-1] + 1]

    return recorded.astype(np.float32), sr48


# ----------------------
# MODO: webapi (HTTP)
# ----------------------
_DISCOVERED_PATH: Optional[str] = None
_CANDIDATE_PATHS: List[str] = [
    "/api/convert",
    "/api/vc/convert",
    "/api/voice/convert",
    "/api/voice",
    "/voice",
    "/infer",
    "/test",
]

def _discover_http_convert_path(base_url: str) -> str:
    # Si el usuario fija explícitamente una ruta, respetarla:
    fixed = os.getenv("RVC_HTTP_CONVERT_PATH", "").strip()
    if fixed:
        return fixed if fixed.startswith("/") else ("/" + fixed)

    # Autodescubrimiento con OPTIONS/HEAD (no 404) y prioridad por rutas más “obvias”
    for p in _CANDIDATE_PATHS:
        url = base_url.rstrip("/") + p
        try:
            r = requests.options(url, timeout=3)
            if r.status_code != 404:
                return p
        except Exception:
            pass
        try:
            r = requests.head(url, timeout=3)
            if r.status_code not in (404, 405, 500):
                return p
        except Exception:
            pass

    # Último intento: aceptar 405 (Method Not Allowed) como indicio de existencia
    for p in _CANDIDATE_PATHS:
        url = base_url.rstrip("/") + p
        try:
            r = requests.options(url, timeout=3)
            if r.status_code in (200, 204, 405):
                return p
        except Exception:
            pass

    raise RuntimeError(
        "No se encontró endpoint HTTP de RVC. "
        "Deja la GUI y usa RVC_MODE=device, o fija RVC_HTTP_CONVERT_PATH en .env."
    )


def _convert_http_wokada(
    wav: np.ndarray, sr: int, *, key: int, f0_method: str, index_rate: float, volume: float
) -> Tuple[np.ndarray, int]:
    """
    Envía audio a un servidor HTTP de RVC (cuando exista). Intentamos multipart clásico:
      file=<wav>, y params como key/f0_method/index_rate/volume/sr/model/index
    """
    base = SETTINGS.wokada_url  # p. ej., http://127.0.0.1:18888
    global _DISCOVERED_PATH

    path = _DISCOVERED_PATH or _discover_http_convert_path(base)
    url = base.rstrip("/") + path

    # WAV temporal
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, wav.astype(np.float32), sr)
        tmp.flush()
        files = {"file": open(tmp.name, "rb")}
        data = {
            "f0": f0_method,
            "key": str(int(key)),
            "index_rate": str(float(index_rate)),
            "volume": str(float(volume)),
            "sr": str(int(sr)),
            # Opcionales: si tu server los usa
            "model": os.getenv("RVC_MODEL_PTH", ""),
            "index": os.getenv("RVC_INDEX_PATH", ""),
        }
        try:
            r = requests.post(url, files=files, data=data, timeout=120)
            if r.status_code == 404:
                # Invalidar y redescubrir 1 vez
                _DISCOVERED_PATH = None
                path2 = _discover_http_convert_path(base)
                if path2 != path:
                    _DISCOVERED_PATH = path2
                    url2 = base.rstrip("/") + path2
                    r = requests.post(url2, files=files, data=data, timeout=120)
            r.raise_for_status()
            return _decode_audio_response(r)
        finally:
            try:
                files["file"].close()
            except Exception:
                pass
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


# ----------------------
# API pública usada por pipeline.py
# ----------------------
def convert(
    wav: np.ndarray, sr: int, *, key: int, f0_method: str, index_rate: float, volume: float, mode: str = "device"
) -> Tuple[np.ndarray, int]:
    """
    mode:
      - "device"  -> VB-Audio + GUI w-Okada (estable hoy)
      - "webapi"  -> servidor HTTP de RVC (si lo tienes levantado)
    """
    mode = (mode or "").lower()
    if mode == "device":
        return _convert_via_devices(wav, sr)
    if mode == "webapi":
        return _convert_http_wokada(wav, sr, key=key, f0_method=f0_method, index_rate=index_rate, volume=volume)
    raise NotImplementedError("Modo RVC no soportado: " + mode)
