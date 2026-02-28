"""
TTS CosyVoice3 - Wrapper Service
Puerto: 8812
Modelo: Fun-CosyVoice3-0.5B (zero-shot / cross-lingual)
Venv: services/tts-cosyvoice/venv  (local)
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
SERVICE_DIR    = Path(__file__).parent
COSYVOICE_REPO = SERVICE_DIR / "repo"
sys.path.insert(0, str(COSYVOICE_REPO))
sys.path.insert(0, str(COSYVOICE_REPO / "third_party" / "Matcha-TTS"))
os.chdir(COSYVOICE_REPO)

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
MODEL_DIR      = str(COSYVOICE_REPO / "pretrained_models" / "Fun-CosyVoice3-0.5B")
REFERENCES_DIR = SERVICE_DIR.parent / "tts" / "reference"
PROMPT_PREFIX  = "You are a helpful assistant.<|endofprompt|>"
PORT           = 8812

app = FastAPI(title="tts-cosyvoice", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global ──────────────────────────────────────────────────────────────
_state: dict = {
    "loaded":    False,
    "loading":   False,
    "error":     None,
    "model":     None,
    "device":    None,
}


# ── Carga del modelo ───────────────────────────────────────────────────────────

def _load_models() -> None:
    _state["loading"] = True
    try:
        from cosyvoice.cli.cosyvoice import AutoModel

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _state["device"] = device

        print(f"[tts-cosyvoice] Cargando modelo desde {MODEL_DIR}...")
        model = AutoModel(model_dir=MODEL_DIR, fp16=False)

        # Fix Blackwell: LLM a float32 para evitar NaN en sm_120
        if hasattr(model, "model") and hasattr(model.model, "llm"):
            model.model.llm = model.model.llm.float()

        _state["model"]   = model
        _state["loaded"]  = True
        print(f"[tts-cosyvoice] Modelo cargado en {device}")
    except Exception as exc:
        _state["error"] = str(exc)
        print(f"[tts-cosyvoice] ERROR al cargar: {exc}")
    finally:
        _state["loading"] = False


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _find_reference(voice: str):
    """
    Retorna (wav_path, transcript_or_None) para la voz indicada.
    Prefiere el par .wav + .txt para zero-shot; si no hay transcript
    usa cross-lingual.
    """
    voice_dir = REFERENCES_DIR / voice
    if voice_dir.exists():
        # Busca par wav+txt con el mismo stem
        for wav in sorted(voice_dir.glob("*.wav")):
            txt = wav.with_suffix(".txt")
            if txt.exists():
                return wav, txt.read_text(encoding="utf-8").strip()
        # Sin transcript: primer wav disponible
        wavs = sorted(voice_dir.glob("*.wav"))
        if wavs:
            return wavs[0], None
    return None, None


def _chunks_to_audio(chunks, sample_rate: int = 24000):
    """Concatena chunks de inference en un array numpy."""
    parts = []
    for chunk in chunks:
        audio_tensor = chunk.get("tts_speech")
        if audio_tensor is not None:
            arr = audio_tensor.squeeze().cpu().numpy()
            parts.append(arr)
    if not parts:
        return np.zeros(0, dtype=np.float32), sample_rate
    return np.concatenate(parts), sample_rate


# ── Endpoints ──────────────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:    str
    voice:   str   = "casiopy"
    speed:   float = 1.0
    emotion: Optional[str] = None


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
        "backend":     "cosyvoice3",
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

        wav_path, transcript = _find_reference(req.voice)
        if wav_path is None:
            raise HTTPException(404, detail=f"Voz '{req.voice}' no encontrada")

        sample_rate = model.sample_rate if hasattr(model, "sample_rate") else 24000

        if transcript:
            # Zero-shot: requiere transcript del audio de referencia
            full_prompt = PROMPT_PREFIX + transcript
            chunks = list(
                model.inference_zero_shot(
                    req.text,
                    full_prompt,
                    str(wav_path),
                    stream=False,
                    speed=req.speed,
                )
            )
        else:
            # Cross-lingual: sin transcript
            full_text = PROMPT_PREFIX + req.text
            chunks = list(
                model.inference_cross_lingual(
                    full_text,
                    str(wav_path),
                    stream=False,
                    speed=req.speed,
                )
            )

        audio, sr = _chunks_to_audio(chunks, sample_rate)
        duration  = len(audio) / sr if sr > 0 else 0

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
            "backend":          "cosyvoice3",
            "mode":             "zero_shot" if transcript else "cross_lingual",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
