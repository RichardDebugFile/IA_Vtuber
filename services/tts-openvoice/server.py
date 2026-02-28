"""
TTS OpenVoice V2 - Wrapper Service
Puerto: 8811
Modelo: MeloTTS ES + ToneColorConverter
Venv: services/tts-openvoice/venv  (local)
"""
import sys
import os
import subprocess

# ── Auto-instalar dependencias de servidor si no están ────────────────────────
def _ensure_deps():
    import importlib.util
    required = {
        "fastapi":    "fastapi",
        "uvicorn":    "uvicorn[standard]",
        "soundfile":  "soundfile",
        "parselmouth": "praat-parselmouth",  # PSOLA — preserva formantes al hacer pitch shift
        "pedalboard": "pedalboard",           # Rubber Band — fallback si parselmouth falla
    }
    missing  = [pkg for mod, pkg in required.items() if importlib.util.find_spec(mod) is None]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])

_ensure_deps()

import io
import base64
import time
import tempfile
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfilt

# ── Rutas del repo (local) ─────────────────────────────────────────────────────
SERVICE_DIR    = Path(__file__).parent
OPENVOICE_REPO = SERVICE_DIR / "repo"
sys.path.insert(0, str(OPENVOICE_REPO))
os.chdir(OPENVOICE_REPO)  # OpenVoice busca checkpoints relativos al CWD

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Constantes ─────────────────────────────────────────────────────────────────
CKPT_DIR       = OPENVOICE_REPO / "checkpoints_v2"
REFERENCES_DIR = SERVICE_DIR.parent / "tts" / "reference"
PORT           = 8811

app = FastAPI(title="tts-openvoice", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global del modelo ───────────────────────────────────────────────────
_state: dict = {
    "loaded":     False,
    "loading":    False,
    "error":      None,
    "tts":        None,
    "tone_conv":  None,
    "speaker_id": None,
    "device":     None,
    "src_se":     None,  # source SE de MeloTTS ES (cacheado en memoria)
    "se_cache":   {},    # voice_name -> target speaker embedding
}

# ── Buffer de auditoría ────────────────────────────────────────────────────────
_synthesis_log: list = []
_LOG_MAX = 40


def _append_log(entry: dict) -> None:
    _synthesis_log.append(entry)
    if len(_synthesis_log) > _LOG_MAX:
        _synthesis_log.pop(0)


# ── Carga de modelos ───────────────────────────────────────────────────────────

def _load_models() -> None:
    _state["loading"] = True
    try:
        from openvoice.api import ToneColorConverter
        from melo.api import TTS

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _state["device"] = device

        # ToneColorConverter
        conv_cfg  = str(CKPT_DIR / "converter" / "config.json")
        conv_ckpt = str(CKPT_DIR / "converter" / "checkpoint.pth")
        # enable_watermark=False → wavmark nunca se carga (evita ruido de fondo
        # causado por el marcado de agua por segmentos cada ~1.5 s)
        tc = ToneColorConverter(conv_cfg, device=device, enable_watermark=False)
        tc.load_ckpt(conv_ckpt)
        _state["tone_conv"] = tc

        # MeloTTS (Español)
        tts = TTS(language="ES", device=device)
        spk_ids = tts.hps.data.spk2id
        # spk2id es HParams (no dict), no tiene .get() — usar "in" + fallback
        sid = spk_ids["ES"] if "ES" in spk_ids else list(spk_ids.values())[0]
        _state["tts"]        = tts
        _state["speaker_id"] = sid

        # Calibrar src_se desde audio real de MeloTTS ES.
        # Es.pth fue creado con voz humana; si MeloTTS genera con características
        # distintas, el modelo extrae mal el contenido lingüístico y la conversión
        # pierde fuerza.  Calibrando desde audio real el src_se es exactamente
        # el embedding de lo que MeloTTS produce, maximizando la diferencia
        # detectable entre src_se y tgt_se.
        src_path = CKPT_DIR / "base_speakers" / "ses" / "es.pth"
        try:
            _tmp_calib = tempfile.mktemp(suffix="_calib_melo.wav")
            tts.tts_to_file(
                "Esta es una prueba de calibracion del sistema de sintesis.",
                sid, _tmp_calib, speed=1.0,
            )
            _state["src_se"] = tc.extract_se([_tmp_calib])
            try:
                os.unlink(_tmp_calib)
            except OSError:
                pass
            norm_calib = round(float(_state["src_se"].norm().item()), 4)
            print(f"[tts-openvoice] src_se calibrado de MeloTTS ES: norm={norm_calib}")
        except Exception as _e_calib:
            print(f"[tts-openvoice] Calibracion src_se fallo ({_e_calib}), usando es.pth")
            _state["src_se"] = torch.load(str(src_path), map_location=device)

        _state["loaded"]     = True

        print(f"[tts-openvoice] Modelos cargados en {device}")
    except Exception as exc:
        _state["error"] = str(exc)
        print(f"[tts-openvoice] ERROR al cargar modelos: {exc}")
    finally:
        _state["loading"] = False


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _find_reference_wavs(voice: str) -> list[Path]:
    """Devuelve TODOS los .wav de referencia para la voz dada.

    Rutas de búsqueda (en orden de prioridad):
      1. <project_root>/<voice>-V2/       → versiones mejoradas por voz
      2. <project_root>/<voice>/          → carpeta raíz con nombre exacto
      3. services/tts/reference/<voice>/  → ubicación legacy
    """
    project_root = SERVICE_DIR.parent.parent.parent

    candidates = [
        project_root / f"{voice}-V2",
        project_root / voice,
        REFERENCES_DIR / voice,
    ]

    for search_dir in candidates:
        if search_dir.exists():
            wavs = sorted(search_dir.glob("*.wav"))
            if wavs:
                print(f"[tts-openvoice] Referencia '{voice}': {len(wavs)} WAV en {search_dir}")
                return wavs

    # Fallback global
    found = [p for p in REFERENCES_DIR.rglob("*.wav") if voice.lower() in p.stem.lower()]
    return sorted(found)


def _get_src_se(device: str):
    """Speaker embedding base de MeloTTS ES (devuelve el valor cacheado)."""
    if _state.get("src_se") is not None:
        return _state["src_se"]
    # Carga de emergencia si no estaba cacheado (no debería ocurrir)
    src_path = CKPT_DIR / "base_speakers" / "ses" / "es.pth"
    _state["src_se"] = torch.load(str(src_path), map_location=device)
    return _state["src_se"]


def _energy_vad(audio: np.ndarray, sr: int,
                frame_ms: int = 30, top_db: float = 35.0) -> np.ndarray:
    """VAD por energía: elimina frames de silencio/ruido de fondo.

    Con ~45% de silencio en los archivos de referencia de casiopy, esto es
    crítico para que extract_se procese solo frames con habla real.
    """
    frame_len = max(1, int(sr * frame_ms / 1000))
    peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 1e-6
    if peak < 1e-8:
        return audio
    threshold = peak * (10.0 ** (-top_db / 20.0))

    speech_frames = [
        audio[i: i + frame_len]
        for i in range(0, len(audio), frame_len)
        if np.max(np.abs(audio[i: i + frame_len])) > threshold
    ]
    if not speech_frames:
        return audio  # fallback: no eliminar nada
    return np.concatenate(speech_frames)


def _get_all_reference_segments(voice: str, target_sr: int = 22050,
                                 segment_sec: float = 10.0) -> list[str]:
    """Prepara segmentos de habla limpia de TODOS los archivos de referencia.

    Pipeline por archivo:
      1. Carga a mono 22050 Hz
      2. High-pass 60 Hz (elimina rumble/DC)
      3. VAD por energía (elimina ~45% de silencio en los archivos de casiopy)
      4. Divide en chunks de ≤10 s para que extract_se promedia más embeddings

    Devuelve lista de rutas temporales .wav listas para pasar a extract_se().
    Importante: el llamador debe borrar los temporales tras usarlos.
    """
    import librosa

    wav_files = _find_reference_wavs(voice)
    if not wav_files:
        return []

    seg_paths: list[str] = []
    seg_len_samples = int(segment_sec * target_sr)

    nyq = target_sr / 2.0
    sos_hp = butter(4, 60.0 / nyq, btype="high", output="sos")

    for wav_file in wav_files:
        audio, _ = librosa.load(str(wav_file), sr=target_sr, mono=True)

        # High-pass para quitar DC y rumble de baja frecuencia
        audio = sosfilt(sos_hp, audio).astype(np.float32)

        # VAD por energía: elimina silencios (crítico con 45% de silencio)
        audio = _energy_vad(audio, target_sr)

        # Muy poco audio después del VAD → descartar
        if len(audio) < target_sr * 1.5:
            print(f"[tts-openvoice] Segmento muy corto tras VAD ({len(audio)/target_sr:.1f}s), descartado: {wav_file.name}")
            continue

        # Dividir en chunks de ~segment_sec
        if len(audio) <= seg_len_samples:
            # Archivo corto: usarlo tal cual
            chunks = [audio]
        else:
            n = max(1, round(len(audio) / seg_len_samples))
            chunk_size = len(audio) // n
            chunks = [audio[i * chunk_size:(i + 1) * chunk_size] for i in range(n)]
            # Descartar chunks demasiado cortos
            chunks = [c for c in chunks if len(c) >= target_sr * 2.0]

        for chunk in chunks:
            tmp = tempfile.mktemp(suffix="_seg.wav")
            sf.write(tmp, chunk, target_sr)
            seg_paths.append(tmp)

    print(f"[tts-openvoice] SE '{voice}': {len(wav_files)} archivo(s) -> {len(seg_paths)} segmento(s) para extract_se")
    return seg_paths


# ── Pitch shift (PSOLA via Praat/parselmouth) ──────────────────────────────────
#
# Comparativa de algoritmos:
#
#  librosa (phase vocoder) → modifica espectrograma STFT: sube pitch Y formantes
#                            → voz suena a "chipmunk" / antinatural
#
#  pedalboard (Rubber Band R2) → mejor que librosa, pero el modo por defecto
#                                 NO activa formant preservation → mismo problema
#
#  WORLD (pyworld) → análisis-resíntesis vocoder; sobre audio de TTS ya vocalizado
#                    por HiFi-GAN produce "double vocoder" (artefactos compuestos)
#
#  PSOLA (Praat) → algoritmo en dominio del tiempo: reordena períodos del sonido.
#                   Solo cambia la duración de los períodos pitch (F0), la envolvente
#                   espectral (formantes) queda intacta por construcción física.
#                   → Resultado natural para voz, sin chipmunk ni vocoder buzz.

def _pitch_shift(audio: np.ndarray, sr: int, n_semitones: float) -> tuple[np.ndarray, str]:
    """Desplaza el tono preservando formantes.  Devuelve (audio, nombre_algoritmo).

    Cascada de calidad:
      1. praat-parselmouth (PSOLA) — preserva formantes por diseño físico
      2. pedalboard (Rubber Band)  — mejor que librosa, sin double-vocoder
      3. librosa (phase vocoder)   — último recurso
    """
    try:
        import parselmouth
        from parselmouth.praat import call

        snd = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=float(sr))
        # Rango 75–600 Hz cubre voz femenina/masculina y TTS española
        manipulation = call(snd, "To Manipulation", 0.01, 75.0, 600.0)
        pitch_tier   = call(manipulation, "Extract pitch tier")
        ratio = 2.0 ** (n_semitones / 12.0)
        call(pitch_tier, "Multiply frequencies", snd.xmin, snd.xmax, ratio)
        call([pitch_tier, manipulation], "Replace pitch tier")
        result = call(manipulation, "Get resynthesis (overlap-add)")
        # result.values → (n_channels, n_samples)
        return result.values[0].astype(np.float32), "psola"

    except Exception as e_psola:
        print(f"[tts-openvoice] parselmouth falló ({e_psola}), usando Rubber Band")
        try:
            from pedalboard import Pedalboard, PitchShift
            board = Pedalboard([PitchShift(semitones=float(n_semitones))])
            return board(audio.astype(np.float32), sample_rate=sr), "rubberband"
        except Exception as e_rb:
            print(f"[tts-openvoice] pedalboard falló ({e_rb}), usando librosa")
            import librosa
            return librosa.effects.pitch_shift(
                audio.astype(np.float32), sr=sr,
                n_steps=n_semitones, res_type="kaiser_best",
            ), "librosa"


# ── Endpoints ──────────────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:        str
    voice:       str   = "casiopy"
    speed:       float = 1.0
    tau:         float = 0.07   # ToneColorConverter: 0.0=fiel a referencia · 1.0=variado
    noise_scale: float = 0.3    # MeloTTS: ruido en síntesis (default interno del modelo: 0.667)
    pitch_shift: float = 0.0    # Semitonos post-conversión (PSOLA). Preserva formantes -> voz natural.
    brightness:  float = 0.0    # dB de realce en altas frecuencias (shelf >=4 kHz). Sin artefactos.
    intensity:   float = 1.0    # Factor de intensidad de conversión: 1.0=normal, >1.0=más agresiva (alpha extrapolation)
    emotion:     Optional[str] = None


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
        "backend":     "openvoice-v2",
        "device":      _state.get("device"),
    }


@app.get("/voices")
def list_voices():
    """Lista voces disponibles buscando en todas las rutas de referencia."""
    voices: set[str] = set()
    project_root = SERVICE_DIR.parent.parent.parent

    # Rutas a inspeccionar
    search_roots = [project_root, REFERENCES_DIR]
    for root in search_roots:
        if not root.exists():
            continue
        for d in root.iterdir():
            if d.is_dir() and any(d.glob("*.wav")):
                # Normalizar nombre: quitar sufijos -V2, -v2, etc.
                name = d.name
                if name.lower().endswith("-v2"):
                    name = name[:-3]
                voices.add(name)

    return {"voices": sorted(voices)}


@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if not _state["loaded"]:
        raise HTTPException(503, detail="Modelo no cargado aún")

    log: dict = {
        "ts":            datetime.now(timezone.utc).isoformat(),
        "voice":         req.voice,
        "tau":           req.tau,
        "noise_scale":   req.noise_scale,
        "pitch_shift":   req.pitch_shift,
        "brightness":    req.brightness,
        "intensity":     req.intensity,
        "speed":         req.speed,
        "text_len":      len(req.text),
        "text_preview":  req.text[:70],
        "se_from_cache": False,
        "se_norm":       None,
        "src_se_norm":   None,
        "cos_sim":       None,
        "t_se_ms":       0,
        "se_segments":   None,   # nº segmentos usados para extract_se (None si vino de caché)
        "t_melo_ms":     0,
        "t_convert_ms":  0,
        "t_pitch_ms":    0,
        "t_bright_ms":   0,
        "pitch_algo":    None,
        "t_total_ms":    0,
        "duration_s":    None,
        "rtf":           None,
        "error":         None,
        "success":       False,
    }

    try:
        t0     = time.time()
        tc     = _state["tone_conv"]
        tts    = _state["tts"]
        sid    = _state["speaker_id"]
        device = _state["device"]

        # ── Speaker embedding (caché o extracción) ────────────────────────────
        t_se = time.time()
        if req.voice not in _state["se_cache"]:
            log["se_from_cache"] = False
            seg_paths: list[str] = []
            try:
                seg_paths = _get_all_reference_segments(req.voice)
                if not seg_paths:
                    log["error"] = f"Voz '{req.voice}' no encontrada"
                    raise HTTPException(404, detail=log["error"])
                tgt_se = tc.extract_se(seg_paths)
                log["se_segments"] = len(seg_paths)
            finally:
                for p in seg_paths:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
            _state["se_cache"][req.voice] = tgt_se
        else:
            log["se_from_cache"] = True
        tgt_se = _state["se_cache"][req.voice]
        log["t_se_ms"] = round((time.time() - t_se) * 1000)

        # Estadísticas del SE objetivo
        try:
            log["se_norm"] = round(float(tgt_se.norm().item()), 4)
        except Exception:
            pass

        src_se = _get_src_se(device)

        # Diagnóstico: similitud entre src_se y tgt_se
        # cos_sim ≈ 1.0 → embeddings muy similares → la conversión no cambiará mucho la voz
        try:
            import torch.nn.functional as F_nn
            src_flat = src_se.flatten().float()
            tgt_flat = tgt_se.flatten().float()
            log["src_se_norm"] = round(float(src_flat.norm().item()), 4)
            log["cos_sim"]     = round(float(
                F_nn.cosine_similarity(src_flat.unsqueeze(0), tgt_flat.unsqueeze(0)).item()
            ), 4)
        except Exception:
            pass

        # ── MeloTTS (síntesis base) ───────────────────────────────────────────
        tmp_base = tempfile.mktemp(suffix=".wav")
        tmp_out  = tempfile.mktemp(suffix=".wav")
        t_melo = time.time()
        tts.tts_to_file(req.text, sid, tmp_base, speed=req.speed, noise_scale=req.noise_scale)
        log["t_melo_ms"] = round((time.time() - t_melo) * 1000)

        # ── Pitch shift PRE-converter ─────────────────────────────────────────
        # Se aplica sobre el audio limpio de MeloTTS (HiFi-GAN directo, sin
        # artefactos del converter) porque:
        #   · Audio limpio → PSOLA produce mínimos artefactos
        #   · ToneColorConverter preserva el pitch de su entrada sin modificarlo
        #   · Si se aplica DESPUÉS del converter, sus propios artefactos se amplifican
        if req.pitch_shift != 0.0:
            t_pitch = time.time()
            audio_pre, sr_pre = sf.read(tmp_base)
            audio_shifted, pitch_algo = _pitch_shift(audio_pre, sr_pre, req.pitch_shift)
            sf.write(tmp_base, audio_shifted, sr_pre)
            log["t_pitch_ms"]  = round((time.time() - t_pitch) * 1000)
            log["pitch_algo"]  = pitch_algo
            print(f"[tts-openvoice] pitch_shift={req.pitch_shift:+.1f}st algo={pitch_algo} t={log['t_pitch_ms']}ms")

        # ── Intensity extrapolation (amplifica dirección src->tgt en espacio de embeddings) ─
        # effective_tgt = src + alpha * (tgt - src)
        # alpha=1.0 → sin cambio; alpha>1.0 → "empuja" tgt más lejos de src → conversión más agresiva
        # Recomendado: 1.0–2.0. Más de 2.0 puede introducir artefactos.
        effective_tgt_se = tgt_se
        if req.intensity != 1.0:
            import torch
            effective_tgt_se = src_se + req.intensity * (tgt_se - src_se)
            print(f"[tts-openvoice] intensity={req.intensity:.2f} -> effective_tgt extrapolado")

        # ── ToneColorConverter ────────────────────────────────────────────────
        t_conv = time.time()
        tc.convert(
            audio_src_path=tmp_base,
            src_se=src_se,
            tgt_se=effective_tgt_se,
            output_path=tmp_out,
            tau=req.tau,
            message="@OpenVoiceV2",
        )
        log["t_convert_ms"] = round((time.time() - t_conv) * 1000)

        audio, sr = sf.read(tmp_out)

        # ── Post-procesado: solo Brightness EQ ───────────────────────────────
        # (el pitch ya se aplicó antes del converter sobre audio limpio)
        if req.brightness != 0.0:
            t_post = time.time()
            gain_linear = 10.0 ** (req.brightness / 20.0)
            nyq = sr / 2.0
            sos = butter(1, 3000.0 / nyq, btype="high", output="sos")
            high_band = sosfilt(sos, audio.astype(np.float32))
            audio = audio + (gain_linear - 1.0) * high_band
            audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
            log["t_bright_ms"] = round((time.time() - t_post) * 1000)

        duration  = len(audio) / sr

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        audio_b64 = base64.b64encode(buf.getvalue()).decode()

        elapsed = time.time() - t0
        log["t_total_ms"] = round(elapsed * 1000)
        log["duration_s"] = round(duration, 3)
        log["rtf"]        = round(elapsed / duration, 3) if duration > 0 else 0
        log["success"]    = True

        for tmp in (tmp_base, tmp_out):
            try:
                os.unlink(tmp)
            except OSError:
                pass

        return {
            "ok":                True,
            "audio_b64":         audio_b64,
            "sample_rate":       sr,
            "duration_s":        round(duration, 3),
            "generation_time_s": round(elapsed, 3),
            "rtf":               round(elapsed / duration, 3) if duration > 0 else 0,
            "backend":           "openvoice-v2",
        }

    except HTTPException:
        raise
    except Exception as exc:
        log["error"] = str(exc)
        raise HTTPException(500, detail=str(exc))
    finally:
        _append_log(log)


@app.get("/logs")
def get_logs():
    """Devuelve el historial de síntesis para auditoría."""
    return {
        "ok":             True,
        "logs":           list(reversed(_synthesis_log)),
        "se_cache_keys":  list(_state["se_cache"].keys()),
        "device":         _state.get("device"),
        "total_calls":    len(_synthesis_log),
    }


@app.post("/cache/clear")
def clear_cache():
    """Vacía el caché de speaker embeddings (fuerza re-extracción en la próxima síntesis)."""
    keys = list(_state["se_cache"].keys())
    _state["se_cache"].clear()
    return {"ok": True, "cleared_keys": keys}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
