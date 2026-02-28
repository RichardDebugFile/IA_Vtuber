"""
TTS Qwen3-TTS - Wrapper Service
Puerto: 8813
Modelo: Qwen3-TTS-12Hz-0.6B-Base
Venv: services/tts-qwen3/venv  (local)
"""
import sys
import os
import subprocess

# ── Auto-instalar dependencias de servidor si no están ────────────────────────
def _ensure_deps():
    import importlib.util
    required = {"fastapi": "fastapi", "uvicorn": "uvicorn[standard]", "soundfile": "soundfile"}
    missing  = [pkg for mod, pkg in required.items() if importlib.util.find_spec(mod) is None]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])

_ensure_deps()

import io
import base64
import time
import asyncio
from pathlib import Path
from typing import Optional

# ── Rutas del repo (local) ─────────────────────────────────────────────────────
SERVICE_DIR = Path(__file__).parent
QWEN3_REPO  = SERVICE_DIR / "repo"
sys.path.insert(0, str(QWEN3_REPO))

import torch
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

import soundfile as sf
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Constantes ─────────────────────────────────────────────────────────────────
MODEL_DIR      = str(QWEN3_REPO / "models" / "Qwen3-TTS-12Hz-0.6B-Base")
REFERENCES_DIR = SERVICE_DIR.parent / "tts" / "reference"
PORT           = 8813

app = FastAPI(title="tts-qwen3", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global ──────────────────────────────────────────────────────────────
_state: dict = {
    "loaded":       False,
    "loading":      False,
    "error":        None,
    "model":        None,
    "device":       None,
    "prompt_cache": {},   # voice_name -> prompt_items
}


# ── Carga del modelo ───────────────────────────────────────────────────────────

def _load_models() -> None:
    _state["loading"] = True
    try:
        from qwen_tts import Qwen3TTSModel

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _state["device"] = device

        print(f"[tts-qwen3] Cargando modelo desde {MODEL_DIR}...")
        model = Qwen3TTSModel.from_pretrained(
            MODEL_DIR,
            device_map=device,
            dtype=torch.bfloat16,
            attn_implementation="sdpa",  # flash_attn no disponible en Windows
        )
        _state["model"]  = model
        _state["loaded"] = True
        print(f"[tts-qwen3] Modelo cargado en {device}")
    except Exception as exc:
        _state["error"] = str(exc)
        print(f"[tts-qwen3] ERROR al cargar: {exc}")
    finally:
        _state["loading"] = False


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _find_reference_wav(voice: str):
    """Retorna (wav_path, txt_transcript_or_None)."""
    voice_dir = REFERENCES_DIR / voice
    if voice_dir.exists():
        # Prefiere el .wav con mayor duración (nombre contiene "15s")
        wavs = sorted(voice_dir.glob("*.wav"), key=lambda p: p.stat().st_size, reverse=True)
        if wavs:
            best = wavs[0]
            # Busca transcript con el mismo stem
            txt = best.with_suffix(".txt")
            transcript = txt.read_text(encoding="utf-8").strip() if txt.exists() else None
            return best, transcript
    return None, None


def _get_prompt_items(voice: str):
    """Retorna prompt_items cacheados (extracción de speaker embedding)."""
    if voice in _state["prompt_cache"]:
        return _state["prompt_cache"][voice]

    model    = _state["model"]
    wav, txt = _find_reference_wav(voice)
    if wav is None:
        return None

    use_icl      = txt is not None
    prompt_items = model.create_voice_clone_prompt(
        ref_audio=str(wav),
        ref_text=txt if use_icl else None,
        x_vector_only_mode=not use_icl,
    )
    _state["prompt_cache"][voice] = prompt_items
    return prompt_items


# ── Endpoints ──────────────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:    str
    voice:   str   = "casiopy"
    speed:   float = 1.0
    emotion: Optional[str] = None   # No soportado directamente en Qwen3-TTS base


@app.on_event("startup")
async def startup() -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_models)


@app.get("/health")
def health():
    # Always return 200 so monitoring shows "online" while model loads
    return {
        "ok":          True,
        "model_loaded": _state["loaded"],
        "loading":     _state["loading"],
        "error":       _state.get("error"),
        "backend":     "qwen3-tts",
        "device":      _state.get("device"),
    }


@app.get("/voices")
def list_voices():
    voices = []
    if REFERENCES_DIR.exists():
        for d in REFERENCES_DIR.iterdir():
            if d.is_dir() and any(d.glob("*.wav")):
                voices.append(d.name)
    return {"voices": voices}


@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if not _state["loaded"]:
        raise HTTPException(503, detail="Modelo no cargado aún")

    try:
        t0    = time.time()
        model = _state["model"]

        # Extrae (o recupera de caché) speaker embedding
        prompt_items = _get_prompt_items(req.voice)
        if prompt_items is None:
            raise HTTPException(404, detail=f"Voz '{req.voice}' no encontrada")

        wavs, sr = model.generate_voice_clone(
            text=req.text,
            language="Spanish",
            voice_clone_prompt=prompt_items,
            non_streaming_mode=True,
        )

        # wavs puede ser tensor o numpy array
        if hasattr(wavs, "cpu"):
            audio = wavs.squeeze().cpu().numpy()
        else:
            audio = np.array(wavs).squeeze()

        if audio.ndim == 0:
            audio = np.array([audio])

        duration = len(audio) / sr if sr > 0 else 0

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        audio_b64 = base64.b64encode(buf.getvalue()).decode()

        elapsed = time.time() - t0

        return {
            "ok":               True,
            "audio_b64":        audio_b64,
            "sample_rate":      sr,
            "duration_s":       round(duration, 3),
            "generation_time_s": round(elapsed, 3),
            "rtf":              round(elapsed / duration, 3) if duration > 0 else 0,
            "backend":          "qwen3-tts",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
