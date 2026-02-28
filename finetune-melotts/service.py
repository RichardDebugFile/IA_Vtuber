"""
Fine-tune MeloTTS — Servicio Web
=================================
Gestiona el pipeline completo desde un navegador.
Puerto: 8820  ->  http://127.0.0.1:8820

Uso:
  python service.py
  (o: run.bat ui)
"""

import asyncio
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Rutas ────────────────────────────────────────────────────────────────────
FINETUNE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = FINETUNE_DIR.parent
DATA_DIR     = FINETUNE_DIR / "data"
LOGS_DIR     = FINETUNE_DIR / "logs" / "casiopy"
OUTPUT_DIR   = FINETUNE_DIR / "output"
STATE_FILE   = DATA_DIR / "pipeline_state.json"
MELO_VENV    = PROJECT_ROOT / "services" / "tts-openvoice" / "venv"
PYTHON_EXE   = MELO_VENV / "Scripts" / "python.exe"

PORT = 8820

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="MeloTTS Fine-tune UI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FINETUNE_DIR / "static")), name="static")

# ── Lazy model cache (Pitch Tester) ───────────────────────────────────────────
_ft_model    = None
_ft_spk_id   = None
_ft_ckpt     = None          # nombre del checkpoint cargado actualmente
_ft_lock     = threading.Lock()
MELO_SITE    = MELO_VENV / "Lib" / "site-packages"


def _ensure_melo_path():
    site = str(MELO_SITE)
    if site not in sys.path:
        sys.path.insert(0, site)


def _load_ft_model_sync():
    """Carga (o recarga si cambió el checkpoint) el modelo fine-tuneado. Thread-safe."""
    global _ft_model, _ft_spk_id, _ft_ckpt
    _ensure_melo_path()
    import torch
    from melo.api import TTS

    ckpt_name = _state.get("last_checkpoint") or _latest_checkpoint()
    if not ckpt_name:
        raise HTTPException(400, "No hay checkpoint. Ejecuta el Paso 3 primero.")

    with _ft_lock:
        if _ft_model is not None and _ft_ckpt == ckpt_name:
            return _ft_model, _ft_spk_id   # ya cargado y es el mismo checkpoint

        ckpt_path   = LOGS_DIR / ckpt_name
        config_path = LOGS_DIR / "config.json"
        if not ckpt_path.exists():
            raise HTTPException(404, f"Checkpoint no encontrado: {ckpt_path}")
        if not config_path.exists():
            raise HTTPException(404, f"Config no encontrado: {config_path}")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model  = TTS(language="ES", device=device, use_hf=False,
                     config_path=str(config_path), ckpt_path=str(ckpt_path))
        spk_ids = model.hps.data.spk2id
        if "casiopy" in spk_ids:
            spk_id = spk_ids["casiopy"]
        elif "ES" in spk_ids:
            spk_id = spk_ids["ES"]
        else:
            spk_id = 0

        _ft_model  = model
        _ft_spk_id = spk_id
        _ft_ckpt   = ckpt_name
        print(f"[finetune-ui] Modelo cargado: {ckpt_name} | device={device} | speaker={spk_id}")
        return model, spk_id


# Parámetros óptimos encontrados para la voz casiopy (testeados con G_24500.pth)
# pitch_shift=+1.0 st  → el modelo fine-tuneado tiende a ser ligeramente grave
# brightness=+2.5 dB   → añade presencia y claridad en altas frecuencias
# noise_scale=0.65      → más variación expresiva (default MeloTTS=0.667, antes usábamos 0.3)
CASIOPY_DEFAULTS = dict(pitch_shift=1.0, brightness=2.5, noise_scale=0.65)


class SynthRequest(BaseModel):
    text:        str
    pitch_shift: float = CASIOPY_DEFAULTS["pitch_shift"]
    speed:       float = 1.0
    brightness:  float = CASIOPY_DEFAULTS["brightness"]
    noise_scale: float = CASIOPY_DEFAULTS["noise_scale"]


def _apply_pitch_shift(audio, sr: int, n_semitones: float):
    """PSOLA vía parselmouth, con fallback a librosa."""
    import numpy as np
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
        return librosa.effects.pitch_shift(audio.astype(np.float32), sr=sr,
                                           n_steps=n_semitones), "librosa"


@app.post("/api/synthesize")
def api_synthesize(req: SynthRequest):
    """Sintetiza texto con el modelo fine-tuneado. Usado por el Pitch Tester."""
    import base64, time
    import numpy as np

    if not req.text.strip():
        raise HTTPException(400, "Texto vacío")

    _ensure_melo_path()
    import soundfile as sf

    model, spk_id = _load_ft_model_sync()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    t0 = time.time()
    try:
        model.tts_to_file(req.text, spk_id, tmp_path,
                          speed=req.speed, noise_scale=req.noise_scale)

        audio, sr = sf.read(tmp_path)
        audio = audio.astype(np.float32)

        pitch_algo = None
        if req.pitch_shift != 0.0:
            audio, pitch_algo = _apply_pitch_shift(audio, sr, req.pitch_shift)

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
            "pitch_algo":        pitch_algo,
            "checkpoint":        _ft_ckpt,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)

# ── Estado global ─────────────────────────────────────────────────────────────
_log_clients: set[asyncio.Queue] = set()
_current_proc: Optional[asyncio.subprocess.Process] = None
_proc_lock = asyncio.Lock()

STEP_NAMES = {
    "1": "Preparar dataset",
    "2": "Fonemizar",
    "3": "Entrenar",
    "4": "Probar",
}


def _load_state() -> dict:
    default = {
        "step_status": {"1": "pending", "2": "pending", "3": "pending", "4": "pending"},
        "current_step": None,
        "running": False,
        "config": {"batch_size": 4, "epochs": 50},
        "metrics": {},
        "last_checkpoint": None,
        "last_error": None,
    }
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for k, v in saved.items():
                default[k] = v
        except Exception:
            pass
    return default


def _save_state():
    DATA_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(_state, indent=2, ensure_ascii=False), encoding="utf-8")


_state = _load_state()
# Al arrancar el servicio, cualquier estado "running" de una sesión anterior es inválido
# (no hay proceso real en ejecución). Limpiarlo para evitar la UI bloqueada.
if _state.get("running"):
    step = _state.get("current_step")
    if step and _state["step_status"].get(step) == "running":
        _state["step_status"][step] = "done"
    _state["running"]      = False
    _state["current_step"] = None
    _save_state()


async def _broadcast(line: str):
    dead = set()
    for q in _log_clients:
        try:
            q.put_nowait(line)
        except asyncio.QueueFull:
            dead.add(q)
    _log_clients.difference_update(dead)


def _parse_metrics(line: str):
    """Extrae métricas de loss del output del entrenamiento."""
    import re
    patterns = [
        r"loss[_/](\w+)\s*[=:]\s*([\d.]+)",
        r"(\w+_loss)\s*[=:]\s*([\d.]+)",
        r"Loss[_/](\w+)\s*[=:]\s*([\d.]+)",
        r"(gen|disc|mel|kl|dur)\s*[=:]\s*([\d.]+)",
    ]
    updated = False
    for pat in patterns:
        for m in re.finditer(pat, line, re.IGNORECASE):
            try:
                _state["metrics"][m.group(1).lower()] = round(float(m.group(2)), 4)
                updated = True
            except ValueError:
                pass
    return updated


def _latest_checkpoint() -> Optional[str]:
    ckpts = sorted(glob.glob(str(LOGS_DIR / "G_*.pth")))
    return Path(ckpts[-1]).name if ckpts else None


async def _run_step_task(step: str, extra_args: list[str]):
    global _current_proc

    scripts = {"1": "1_prepare_dataset.py", "2": "2_preprocess.py",
               "3": "3_train.py",           "4": "4_test.py"}

    cmd = [str(PYTHON_EXE), str(FINETUNE_DIR / scripts[step])] + extra_args
    _state["current_step"] = step
    _state["running"]      = True
    _state["step_status"][step] = "running"
    _state["last_error"]   = None
    _save_state()

    await _broadcast(f"[UI] ▶ Paso {step}: {STEP_NAMES[step]}")
    await _broadcast(f"[UI]   {' '.join(cmd)}")

    try:
        env = os.environ.copy()
        env["PATH"] = str(MELO_VENV / "Scripts") + os.pathsep + env.get("PATH", "")
        env.setdefault("LOCAL_RANK", "0")
        env["USE_LIBUV"] = "0"         # PyTorch en Windows sin libuv
        env["PYTHONUNBUFFERED"] = "1"  # Flush inmediato de stdout/stderr al stream de la UI

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(FINETUNE_DIR),
            env=env,
        )
        async with _proc_lock:
            _current_proc = proc

        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            await _broadcast(line)
            _parse_metrics(line)
            _state["last_checkpoint"] = _latest_checkpoint()

        await proc.wait()
        # Si stop() ya marcó el paso como "done", respetar esa decisión
        if _state["step_status"].get(step) == "running":
            ok = proc.returncode == 0
            _state["step_status"][step] = "done" if ok else "error"
            _state["last_checkpoint"] = _latest_checkpoint()
            msg = f"[UI] {'✓' if ok else '✗'} Paso {step} {'completado' if ok else f'terminó con error (código {proc.returncode})'}"
            await _broadcast(msg)

    except Exception as e:
        _state["step_status"][step] = "error"
        _state["last_error"] = str(e)
        await _broadcast(f"[UI] ✗ Error en paso {step}: {e}")
    finally:
        _state["running"]      = False
        _state["current_step"] = None
        async with _proc_lock:
            _current_proc = None
        _save_state()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(FINETUNE_DIR / "static" / "index.html"))


@app.get("/api/status")
def status():
    _state["last_checkpoint"] = _latest_checkpoint()
    return _state


@app.post("/api/run/{step}")
async def run_step(step: str):
    # FastAPI resuelve /api/run/all hacia esta ruta paramétrica — delegamos explícitamente
    if step == "all":
        return await run_all()
    if _state["running"]:
        raise HTTPException(409, "Ya hay un proceso en ejecución. Detenerlo primero.")
    if step not in STEP_NAMES:
        raise HTTPException(400, f"Paso inválido: {step}")

    extra = []
    if step == "3":
        # Auto-resume si ya hay checkpoints; pasar config actual
        if _latest_checkpoint():
            extra = ["--resume"]
        batch = _state["config"].get("batch_size", 16)
        extra += ["--batch-size", str(batch)]

    asyncio.create_task(_run_step_task(step, extra))
    return {"ok": True, "step": step}


@app.post("/api/run/all")
async def run_all():
    if _state["running"]:
        raise HTTPException(409, "Ya hay un proceso en ejecución.")

    async def _chain():
        for step in ["1", "2", "3"]:
            # Saltar pasos ya completados
            if _state["step_status"][step] == "done":
                await _broadcast(f"[UI] ⏭ Paso {step} ya completado, saltando.")
                continue
            extra = []
            if step == "3":
                if _latest_checkpoint():
                    extra = ["--resume"]
                batch = _state["config"].get("batch_size", 16)
                extra += ["--batch-size", str(batch)]
            await _run_step_task(step, extra)
            if _state["step_status"][step] != "done":
                await _broadcast("[UI] ✗ Pipeline detenido por error.")
                return
        await _broadcast("[UI] ✓ Pipeline completo. Ejecuta el Paso 4 para escuchar el resultado.")

    asyncio.create_task(_chain())
    return {"ok": True}


@app.post("/api/stop")
async def stop():
    global _current_proc
    async with _proc_lock:
        proc = _current_proc
    if proc and proc.returncode is None:
        # Actualizar estado ANTES de matar para que pollStatus() refleje el cambio inmediatamente
        step = _state.get("current_step")
        if step:
            _state["step_status"][step] = "done"  # detenido intencionalmente = checkpoint válido
        _state["running"]      = False
        _state["current_step"] = None
        _state["last_checkpoint"] = _latest_checkpoint()
        _save_state()
        # Matar árbol de procesos (3_train.py + torchrun + workers)
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=5)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        await _broadcast("[UI] ⏹ Proceso detenido por el usuario. Checkpoint guardado.")
        return {"ok": True}
    return {"ok": False, "message": "No hay proceso activo"}


@app.post("/api/reset/{step}")
async def reset_step(step: str):
    if _state["running"]:
        raise HTTPException(409, "Detén el proceso antes de resetear.")
    if step not in STEP_NAMES:
        raise HTTPException(400)
    _state["step_status"][step] = "pending"
    _save_state()
    return {"ok": True}


class ConfigIn(BaseModel):
    batch_size: Optional[int] = None
    epochs: Optional[int] = None


@app.post("/api/config")
def update_config(cfg: ConfigIn):
    if cfg.batch_size:
        _state["config"]["batch_size"] = max(1, min(64, cfg.batch_size))
    if cfg.epochs:
        _state["config"]["epochs"] = max(10, min(500, cfg.epochs))
    _save_state()
    # Sincronizar con data/config.json si ya fue generado
    train_cfg = DATA_DIR / "config.json"
    if train_cfg.exists():
        try:
            c = json.loads(train_cfg.read_text(encoding="utf-8"))
            if cfg.batch_size:
                c["train"]["batch_size"] = _state["config"]["batch_size"]
            if cfg.epochs:
                c["train"]["epochs"] = _state["config"]["epochs"]
            train_cfg.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return {"ok": True, "config": _state["config"]}


@app.get("/api/outputs")
def list_outputs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = sorted(OUTPUT_DIR.glob("*.wav"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "url": f"/api/outputs/{f.name}",
             "type": "casiopy" if "casiopy" in f.name else "base"} for f in files]


@app.get("/api/outputs/{filename}")
def get_output(filename: str):
    f = OUTPUT_DIR / filename
    if not f.exists() or not f.parent == OUTPUT_DIR:
        raise HTTPException(404)
    return FileResponse(str(f), media_type="audio/wav")


@app.get("/api/logs")
async def log_stream(request: Request):
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _log_clients.add(q)

    async def generate():
        try:
            q.put_nowait("[UI] Conectado al stream de logs.")
            while True:
                if await request.is_disconnected():
                    break
                try:
                    line = await asyncio.wait_for(q.get(), timeout=5.0)
                    safe = line.replace("\n", "\\n")
                    yield f"data: {safe}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _log_clients.discard(q)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── Main ──────────────────────────────────────────────────────────────────────
def _suppress_connection_reset(loop, context):
    """Suppresses benign WinError 10054 noise from ProactorEventLoop on Windows."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)


if __name__ == "__main__":
    if not PYTHON_EXE.exists():
        print(f"[ERROR] Venv de tts-openvoice no encontrado: {PYTHON_EXE}")
        sys.exit(1)
    # Suppress benign "connection reset by peer" noise on Windows
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(_suppress_connection_reset)
    asyncio.set_event_loop(loop)
    print(f"[finetune-ui] Abriendo http://127.0.0.1:{PORT}")
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", loop="none")
