"""
TTS Fish Speech (Local) - Wrapper Service
Puerto: 8814
Modelo: openaudio-s1-mini (Llama + VQ-GAN codec)
Venv: services/tts-fish/venv  (local)
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
FISH_REPO   = SERVICE_DIR / "repo"
sys.path.insert(0, str(FISH_REPO))
os.chdir(FISH_REPO)  # fish-speech espera CWD = repo root

import torch
import soundfile as sf
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Constantes ─────────────────────────────────────────────────────────────────
LLAMA_CKPT     = str(FISH_REPO / "checkpoints" / "openaudio-s1-mini")
DECODER_CKPT   = str(FISH_REPO / "checkpoints" / "openaudio-s1-mini" / "codec.pth")
REFERENCES_DIR = SERVICE_DIR.parent / "tts" / "reference"
PORT           = 8814

app = FastAPI(title="tts-fish", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global ──────────────────────────────────────────────────────────────
_state: dict = {
    "loaded":  False,
    "loading": False,
    "error":   None,
    "engine":  None,
    "device":  None,
}


# ── Carga del modelo ───────────────────────────────────────────────────────────

def _load_models() -> None:
    _state["loading"] = True
    try:
        from tools.server.model_manager import ModelManager

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _state["device"] = device

        print(f"[tts-fish] Cargando openaudio-s1-mini en {device}...")
        manager = ModelManager(
            mode="tts",
            device=device,
            half=False,
            compile=False,
            llama_checkpoint_path=LLAMA_CKPT,
            decoder_checkpoint_path=DECODER_CKPT,
            decoder_config_name="modded_dac_vq",
        )
        _state["engine"] = manager.tts_inference_engine
        _state["loaded"] = True
        print("[tts-fish] Modelo cargado")
    except Exception as exc:
        _state["error"] = str(exc)
        print(f"[tts-fish] ERROR al cargar: {exc}")
    finally:
        _state["loading"] = False


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _find_reference_wav(voice: str) -> Optional[Path]:
    voice_dir = REFERENCES_DIR / voice
    if voice_dir.exists():
        # Prefiere wav de mayor tamaño (más referencia = mejor calidad)
        wavs = sorted(voice_dir.glob("*.wav"), key=lambda p: p.stat().st_size, reverse=True)
        if wavs:
            return wavs[0]
    for wav in REFERENCES_DIR.rglob("*.wav"):
        if voice.lower() in wav.stem.lower():
            return wav
    return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:        str
    voice:       str   = "casiopy"
    speed:       float = 1.0
    emotion:     Optional[str] = None
    temperature: float = 0.8
    top_p:       float = 0.8


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
        "backend":     "fish-speech-local",
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
        from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio

        t0     = time.time()
        engine = _state["engine"]

        ref_wav = _find_reference_wav(req.voice)
        if ref_wav is None:
            raise HTTPException(404, detail=f"Voz '{req.voice}' no encontrada")

        ref_bytes = ref_wav.read_bytes()

        tts_req = ServeTTSRequest(
            text=req.text,
            references=[ServeReferenceAudio(audio=ref_bytes, text="")],
            format="wav",
            chunk_length=200,
            temperature=req.temperature,
            top_p=req.top_p,
            repetition_penalty=1.1,
            max_new_tokens=1024,
            stream=False,
        )

        # Recoger audio del engine
        audio_parts = []
        sr          = 44100  # fish-speech default
        for result in engine.inference(tts_req):
            if result.code == "final" and result.audio is not None:
                sr_r, arr = result.audio
                sr = sr_r
                audio_parts.append(arr)
            elif result.code == "segment" and result.audio is not None:
                sr_r, arr = result.audio
                sr = sr_r
                audio_parts.append(arr)

        if not audio_parts:
            raise HTTPException(500, detail="Engine no generó audio")

        audio    = np.concatenate(audio_parts)
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
            "backend":          "fish-speech-local",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
