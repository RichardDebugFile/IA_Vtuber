import hashlib, os
from typing import Tuple
import numpy as np
import soundfile as sf
from .config import SETTINGS
from .tts.fish_client import synthesize
from .vc.rvc_client import convert
from .cache.audio_cache import AudioCache
from .clients.gateway_ws import publish_audio
import logging
log = logging.getLogger("pipeline")

CACHE = AudioCache(SETTINGS.save_wav_dir, max_items=SETTINGS.cache_max_items, max_mb=SETTINGS.cache_max_mb)

def _key_hash(text: str, emotion: str | None, style: str | None, sr: int, rvc_enabled: bool, rvc_opts: dict) -> str:
    h = hashlib.sha1()
    h.update(("text="+text).encode("utf-8"))
    h.update(("emotion="+str(emotion)).encode("utf-8"))
    h.update(("style="+str(style)).encode("utf-8"))
    h.update(("sr="+str(sr)).encode("utf-8"))
    h.update(("rvc="+str(rvc_enabled)).encode("utf-8"))
    h.update(("opts="+str(sorted(rvc_opts.items()))).encode("utf-8"))
    return h.hexdigest()

def _save_wav(y: np.ndarray, sr: int, path: str):
    sf.write(path, y, sr)

log.info("TTS base=%s path=%s", SETTINGS.fish_base, getattr(SETTINGS, "fish_tts_path", None))

def run_tts_vc(text: str, emotion: str | None, style: str | None, speaker_id: str | None, rvc_opts: dict, want_sr: int | None = None) -> Tuple[str, float]:
    sr0 = want_sr or SETTINGS.fish_sr

    key = _key_hash(text, emotion, style, sr0, bool(rvc_opts.get("enabled", True)), rvc_opts)
    cached = CACHE.get(key)
    if cached:
        return cached, 0.0

    # 1) TTS (Fish)
    if not SETTINGS.fish_enable:
        raise RuntimeError("Fish TTS deshabilitado (FISH_ENABLE=false)")

    y, sr = synthesize(text, emotion or SETTINGS.fish_emotion_default, style, sr0)

    # 2) VC (RVC)
    if SETTINGS.rvc_enable and rvc_opts.get("enabled", True):
        y, sr = convert(
            y, sr,
            key=int(rvc_opts.get("key", SETTINGS.rvc_key)),
            f0_method=str(rvc_opts.get("f0_method", SETTINGS.rvc_f0_method)),
            index_rate=float(rvc_opts.get("index_rate", SETTINGS.rvc_index_rate)),
            volume=float(rvc_opts.get("volume", SETTINGS.rvc_volume)),
            mode=SETTINGS.rvc_mode
        )

    # 3) guardar + cache
    out_path = os.path.join(SETTINGS.save_wav_dir, f"{key}.wav")
    _save_wav(y, sr, out_path)
    CACHE.put(key, out_path)

    # 4) publicar (opcional)
    if SETTINGS.publish_audio_events:
        publish_audio(out_path, text, emotion)

    # duración aprox
    dur = len(y) / float(sr) if len(y) else 0.0
    return out_path, dur
