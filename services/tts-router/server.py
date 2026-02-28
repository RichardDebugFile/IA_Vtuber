"""
TTS Router - Enrutador central de síntesis de voz
Puerto: 8810

Modos disponibles:
  casiopy        → Casiopy FT      :8815  (RTF ~1.5, voz fine-tuneada, DEFAULT)
  stream_fast    → OpenVoice V2    :8811  (RTF ~0.74, velocidad, voz base ES)
  stream_quality → CosyVoice3      :8812  (RTF ~2.1,  calidad)
  content        → Qwen3-TTS       :8813  (RTF ~6.3,  contenido)
  content_fish   → Fish Speech     :8814  (RTF ~4.2,  contenido local)

Process management:
  POST /backends/{mode}/start  → inicia el proceso backend
  POST /backends/{mode}/stop   → detiene el proceso backend
  POST /backends/stopall       → detiene todos los backends
  GET  /backends               → estado completo (HTTP + proceso)
  GET  /backends/{mode}        → estado de un backend específico
"""
import asyncio
import base64
import io
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

# ── Rutas base ────────────────────────────────────────────────────────────────
ROUTER_DIR   = Path(__file__).parent
SERVICES_DIR = ROUTER_DIR.parent   # services/

# ── Configuración de backends ──────────────────────────────────────────────────
BACKENDS = {
    "casiopy": {
        "name":    "Casiopy FT (MeloTTS fine-tuneado)",
        "url":     "http://127.0.0.1:8815",
        "health":  "http://127.0.0.1:8815/health",
        "timeout": 60.0,
        "python":  SERVICES_DIR / "tts-openvoice" / "venv" / "Scripts" / "python.exe",
        "script":  SERVICES_DIR / "tts-casiopy" / "server.py",
    },
    "stream_fast": {
        "name":    "OpenVoice V2",
        "url":     "http://127.0.0.1:8811",
        "health":  "http://127.0.0.1:8811/health",
        "timeout": 60.0,
        "python":  SERVICES_DIR / "tts-openvoice" / "venv" / "Scripts" / "python.exe",
        "script":  SERVICES_DIR / "tts-openvoice" / "server.py",
    },
    "stream_quality": {
        "name":    "CosyVoice3",
        "url":     "http://127.0.0.1:8812",
        "health":  "http://127.0.0.1:8812/health",
        "timeout": 120.0,
        "python":  SERVICES_DIR / "tts-cosyvoice" / "venv" / "Scripts" / "python.exe",
        "script":  SERVICES_DIR / "tts-cosyvoice" / "server.py",
    },
    "content": {
        "name":    "Qwen3-TTS",
        "url":     "http://127.0.0.1:8813",
        "health":  "http://127.0.0.1:8813/health",
        "timeout": 300.0,
        "python":  SERVICES_DIR / "tts-qwen3" / "venv" / "Scripts" / "python.exe",
        "script":  SERVICES_DIR / "tts-qwen3" / "server.py",
    },
    "content_fish": {
        "name":    "Fish Speech (local)",
        "url":     "http://127.0.0.1:8814",
        "health":  "http://127.0.0.1:8814/health",
        "timeout": 300.0,
        "python":  SERVICES_DIR / "tts-fish" / "venv" / "Scripts" / "python.exe",
        "script":  SERVICES_DIR / "tts-fish" / "server.py",
    },
}

DEFAULT_MODE = "casiopy"
PORT         = 8810

# ── Procesos gestionados por el router ────────────────────────────────────────
_procs: dict = {}   # mode -> subprocess.Popen

app = FastAPI(title="tts-router", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelo de request ─────────────────────────────────────────────────────────

class SynthRequest(BaseModel):
    text:    str
    voice:   str   = "casiopy"
    mode:    str   = DEFAULT_MODE
    speed:   float = 1.0
    emotion: Optional[str] = None


# ── Helpers de proceso ─────────────────────────────────────────────────────────

def _proc_running(mode: str) -> bool:
    proc = _procs.get(mode)
    return proc is not None and proc.poll() is None


def _launch_proc(mode: str) -> subprocess.Popen:
    """Lanza el proceso backend con su venv propio."""
    cfg    = BACKENDS[mode]
    python = cfg["python"]
    script = cfg["script"]

    if not python.exists():
        raise RuntimeError(
            f"Venv no encontrado: {python}\n"
            f"Ejecuta setup_venv.bat en la carpeta del servicio."
        )
    if not script.exists():
        raise RuntimeError(f"Script no encontrado: {script}")

    return subprocess.Popen(
        [str(python), str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def _kill_proc(mode: str) -> None:
    """Termina el proceso del backend si estaba corriendo."""
    proc = _procs.pop(mode, None)
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ── Ciclo de vida ─────────────────────────────────────────────────────────────

@app.on_event("shutdown")
async def _on_shutdown():
    """Detiene todos los backends al cerrar el router."""
    for mode in list(_procs.keys()):
        _kill_proc(mode)


# ── Endpoints de gestión de procesos ─────────────────────────────────────────

@app.post("/backends/{mode}/start")
async def start_backend(mode: str):
    """Inicia el proceso backend indicado en su propio venv."""
    if mode not in BACKENDS:
        raise HTTPException(
            404,
            detail=f"Backend '{mode}' desconocido. Opciones: {list(BACKENDS)}",
        )

    if _proc_running(mode):
        return {
            "ok":      True,
            "pid":     _procs[mode].pid,
            "message": f"Backend '{mode}' ya estaba corriendo",
        }

    try:
        proc = _launch_proc(mode)
    except RuntimeError as exc:
        raise HTTPException(500, detail=str(exc))

    _procs[mode] = proc
    return {
        "ok":      True,
        "pid":     proc.pid,
        "message": (
            f"Backend '{BACKENDS[mode]['name']}' iniciando (pid={proc.pid}). "
            f"Sondea GET /backends/{mode} hasta que model_loaded=true."
        ),
    }


@app.post("/backends/{mode}/stop")
async def stop_backend(mode: str):
    """Detiene el proceso backend indicado."""
    if mode not in BACKENDS:
        raise HTTPException(404, detail=f"Backend '{mode}' desconocido")

    if not _proc_running(mode):
        _procs.pop(mode, None)
        return {"ok": True, "message": f"Backend '{mode}' no estaba corriendo"}

    pid = _procs[mode].pid
    _kill_proc(mode)
    return {"ok": True, "message": f"Backend '{mode}' detenido (pid={pid})"}


@app.post("/backends/stopall")
async def stop_all():
    """Detiene todos los backends gestionados por el router."""
    stopped = [m for m in list(_procs.keys()) if _proc_running(m)]
    for mode in list(_procs.keys()):
        _kill_proc(mode)
    return {"ok": True, "stopped": stopped}


# ── Endpoints de estado ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "ok":      True,
        "service": "tts-router",
        "backends": list(BACKENDS.keys()),
        "running":  [m for m in BACKENDS if _proc_running(m)],
    }


@app.get("/backends")
async def list_backends():
    """Estado completo de todos los backends (HTTP + proceso)."""
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for mode, cfg in BACKENDS.items():
            proc_alive = _proc_running(mode)
            pid        = _procs[mode].pid if proc_alive else None

            t0 = time.time()
            try:
                resp    = await client.get(cfg["health"])
                latency = (time.time() - t0) * 1000
                online  = resp.status_code == 200
                hdata   = resp.json() if online else {}
                results[mode] = {
                    "name":            cfg["name"],
                    "mode":            mode,
                    "url":             cfg["url"],
                    "online":          online,
                    "latency_ms":      round(latency, 2),
                    "model_loaded":    hdata.get("model_loaded", False),
                    "loading":         hdata.get("loading", False),
                    "error":           hdata.get("error"),
                    "device":          hdata.get("device"),
                    "process_running": proc_alive,
                    "pid":             pid,
                }
            except Exception as exc:
                results[mode] = {
                    "name":            cfg["name"],
                    "mode":            mode,
                    "url":             cfg["url"],
                    "online":          False,
                    "error":           str(exc),
                    "model_loaded":    False,
                    "loading":         False,
                    "process_running": proc_alive,
                    "pid":             pid,
                }
    return results


@app.get("/backends/{mode}")
async def backend_status(mode: str):
    """Estado de un backend específico (solo consulta ese backend)."""
    if mode not in BACKENDS:
        raise HTTPException(404, detail=f"Backend '{mode}' desconocido")

    cfg        = BACKENDS[mode]
    proc_alive = _proc_running(mode)
    pid        = _procs[mode].pid if proc_alive else None

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(cfg["health"])
        latency = (time.time() - t0) * 1000
        online  = resp.status_code == 200
        hdata   = resp.json() if online else {}
        return {
            "name":            cfg["name"],
            "mode":            mode,
            "url":             cfg["url"],
            "online":          online,
            "latency_ms":      round(latency, 2),
            "model_loaded":    hdata.get("model_loaded", False),
            "loading":         hdata.get("loading", False),
            "error":           hdata.get("error"),
            "device":          hdata.get("device"),
            "process_running": proc_alive,
            "pid":             pid,
        }
    except Exception as exc:
        return {
            "name":            cfg["name"],
            "mode":            mode,
            "url":             cfg["url"],
            "online":          False,
            "error":           str(exc),
            "model_loaded":    False,
            "loading":         False,
            "process_running": proc_alive,
            "pid":             pid,
        }


@app.get("/voices")
async def list_voices():
    """Lista voces disponibles (consulta al primer backend online)."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for cfg in BACKENDS.values():
            try:
                resp = await client.get(f"{cfg['url']}/voices")
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                continue
    return {"voices": []}


# ── Endpoints de síntesis ─────────────────────────────────────────────────────

@app.post("/synthesize")
async def synthesize(req: SynthRequest):
    """
    Sintetiza texto enrutando al backend apropiado según `mode`.
    Respuesta: { ok, audio_b64, sample_rate, duration_s, rtf, backend, mode }
    """
    if req.mode not in BACKENDS:
        raise HTTPException(
            400,
            detail=f"Modo '{req.mode}' desconocido. Opciones: {list(BACKENDS.keys())}",
        )

    backend = BACKENDS[req.mode]
    payload = {
        "text":    req.text,
        "voice":   req.voice,
        "speed":   req.speed,
        "emotion": req.emotion,
    }

    try:
        async with httpx.AsyncClient(timeout=backend["timeout"]) as client:
            resp = await client.post(
                f"{backend['url']}/synthesize",
                json=payload,
            )

        if resp.status_code == 503:
            raise HTTPException(
                503,
                detail=f"Backend '{backend['name']}' no está listo (modelo cargando o apagado)",
            )
        if resp.status_code == 404:
            raise HTTPException(404, detail=resp.json().get("detail", "Recurso no encontrado"))
        if resp.status_code != 200:
            raise HTTPException(
                resp.status_code,
                detail=f"Error en backend: {resp.text[:300]}",
            )

        data = resp.json()
        data["mode"] = req.mode
        return data

    except httpx.ConnectError:
        raise HTTPException(
            503,
            detail=(
                f"Backend '{backend['name']}' ({backend['url']}) no accesible. "
                f"Usa POST /backends/{req.mode}/start para iniciarlo."
            ),
        )
    except httpx.TimeoutException:
        raise HTTPException(
            504,
            detail=f"Backend '{backend['name']}' superó el tiempo límite ({backend['timeout']}s)",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@app.post("/synthesize/wav")
async def synthesize_wav(req: SynthRequest):
    """Igual que /synthesize pero devuelve el audio directamente como audio/wav."""
    result = await synthesize(req)
    audio_bytes = base64.b64decode(result["audio_b64"])
    return Response(content=audio_bytes, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
