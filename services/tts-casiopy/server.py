"""
TTS Casiopy — Servicio de voz fine-tuneada
==========================================
Puerto: 8815

Usa el checkpoint fine-tuneado de MeloTTS (casiopy) directamente.
Sin ToneColorConverter — el modelo ya habla como casiopy.

Parámetros óptimos hallados con Pitch Tester (G_24500.pth):
  pitch_shift = +1.0 st   (modelo tiende a ser ligeramente grave)
  brightness  = +2.5 dB   (presencia en altas frecuencias)
  noise_scale = 0.65       (variación expresiva)

El servicio escanea model/ y usa el checkpoint G_*.pth más reciente,
por lo que al copiar un nuevo checkpoint basta con reiniciar el servicio.
"""

import base64
import glob
import io
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Rutas ──────────────────────────────────────────────────────────────────────
SERVICE_DIR  = Path(__file__).parent.resolve()
SERVICES_DIR = SERVICE_DIR.parent
MODEL_DIR    = SERVICE_DIR / "model"
MELO_SITE    = SERVICES_DIR / "tts-openvoice" / "venv" / "Lib" / "site-packages"

PORT = 8815

# Añadir el venv de tts-openvoice al path (melo, torch, soundfile, etc.)
if str(MELO_SITE) not in sys.path:
    sys.path.insert(0, str(MELO_SITE))

# ── Defaults óptimos (Pitch Tester, G_24500.pth) ──────────────────────────────
DEFAULT_PITCH_SHIFT = 1.0    # semitones
DEFAULT_BRIGHTNESS  = 2.5    # dB high-shelf boost ≥3 kHz
DEFAULT_NOISE_SCALE = 0.65   # síntesis MeloTTS (0=determinista, 1=variable)

# ── Estado global ──────────────────────────────────────────────────────────────
_model      = None
_spk_id     = None
_ckpt_name  = None
_loading    = False
_load_error = None

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="tts-casiopy", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_latest_checkpoint() -> Optional[Path]:
    """Devuelve el G_*.pth más reciente en model/."""
    files = sorted(glob.glob(str(MODEL_DIR / "G_*.pth")))
    return Path(files[-1]) if files else None


def _load_model():
    global _model, _spk_id, _ckpt_name, _loading, _load_error
    _loading    = True
    _load_error = None
    try:
        import torch
        from melo.api import TTS

        ckpt_path   = _find_latest_checkpoint()
        config_path = MODEL_DIR / "config.json"

        if ckpt_path is None:
            raise FileNotFoundError(f"No hay checkpoint G_*.pth en {MODEL_DIR}")
        if not config_path.exists():
            raise FileNotFoundError(f"Config no encontrado: {config_path}")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[tts-casiopy] Cargando {ckpt_path.name} en {device}...")

        model = TTS(
            language="ES",
            device=device,
            use_hf=False,
            config_path=str(config_path),
            ckpt_path=str(ckpt_path),
        )

        spk_ids = model.hps.data.spk2id
        if "casiopy" in spk_ids:
            spk_id = spk_ids["casiopy"]
        elif "ES" in spk_ids:
            spk_id = spk_ids["ES"]
        else:
            spk_id = 0

        _model     = model
        _spk_id    = spk_id
        _ckpt_name = ckpt_path.name
        print(f"[tts-casiopy] Listo | checkpoint={_ckpt_name} device={device} speaker_id={spk_id}")

    except Exception as exc:
        _load_error = str(exc)
        print(f"[tts-casiopy] ERROR al cargar modelo: {exc}")
    finally:
        _loading = False


def _pitch_shift(audio: np.ndarray, sr: int, n_semitones: float):
    """PSOLA via parselmouth → fallback librosa."""
    try:
        import parselmouth
        from parselmouth.praat import call
        snd   = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=float(sr))
        manip = call(snd, "To Manipulation", 0.01, 75.0, 600.0)
        pt    = call(manip, "Extract pitch tier")
        call(pt, "Multiply frequencies", snd.xmin, snd.xmax, 2.0 ** (n_semitones / 12.0))
        call([pt, manip], "Replace pitch tier")
        result = call(manip, "Get resynthesis (overlap-add)")
        return result.values[0].astype(np.float32), "psola"
    except Exception:
        import librosa
        shifted = librosa.effects.pitch_shift(
            audio.astype(np.float32), sr=sr,
            n_steps=n_semitones, res_type="kaiser_best",
        )
        return shifted, "librosa"


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    threading.Thread(target=_load_model, daemon=True).start()


# ── Request model ──────────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:        str
    voice:       str   = "casiopy"          # informativo, solo hay una voz
    speed:       float = 1.0
    pitch_shift: float = DEFAULT_PITCH_SHIFT
    brightness:  float = DEFAULT_BRIGHTNESS
    noise_scale: float = DEFAULT_NOISE_SCALE
    emotion:     Optional[str] = None       # reservado para compatibilidad futura


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "ok":           _model is not None,
        "service":      "tts-casiopy",
        "model_loaded": _model is not None,
        "loading":      _loading,
        "error":        _load_error,
        "checkpoint":   _ckpt_name,
        "device":       str(_model.device) if _model is not None else None,
    }


@app.get("/voices")
def voices():
    return {
        "voices": [
            {
                "id":      "casiopy",
                "name":    "Casiopy",
                "lang":    "ES",
                "model":   _ckpt_name,
                "backend": "melo-ft",
            }
        ]
    }


@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if _loading:
        raise HTTPException(503, detail="Modelo cargando, intenta en unos segundos")
    if _model is None:
        raise HTTPException(503, detail=f"Modelo no disponible: {_load_error or 'desconocido'}")
    if not req.text.strip():
        raise HTTPException(400, detail="Texto vacío")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    t0 = time.time()
    try:
        _model.tts_to_file(
            req.text, _spk_id, tmp_path,
            speed=req.speed, noise_scale=req.noise_scale,
        )

        audio, sr = sf.read(tmp_path)
        audio = audio.astype(np.float32)

        pitch_algo = None
        if req.pitch_shift != 0.0:
            audio, pitch_algo = _pitch_shift(audio, sr, req.pitch_shift)

        if req.brightness != 0.0:
            from scipy.signal import butter, sosfilt
            gain = 10.0 ** (req.brightness / 20.0)
            sos  = butter(1, 3000.0 / (sr / 2.0), btype="high", output="sos")
            high = sosfilt(sos, audio)
            audio = np.clip(audio + (gain - 1.0) * high, -1.0, 1.0).astype(np.float32)

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        elapsed  = time.time() - t0
        duration = len(audio) / sr

        return {
            "ok":                True,
            "audio_b64":         base64.b64encode(buf.getvalue()).decode(),
            "sample_rate":       sr,
            "duration_s":        round(duration, 3),
            "generation_time_s": round(elapsed, 3),
            "rtf":               round(elapsed / duration, 3) if duration > 0 else 0,
            "backend":           "casiopy-ft",
            "checkpoint":        _ckpt_name,
            "pitch_algo":        pitch_algo,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
