"""
Monitoring Service - Sistema de Monitoreo y Control de Microservicios
Puerto: 8900
"""
from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import httpx
from fastapi import FastAPI, HTTPException, Response, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import audit_logger
from .monitoring import monitoring, DockerMonitor, ServiceState

app = FastAPI(title="Monitoring Service Dashboard", version="2.0.0")

# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections[:]:  # Copy list to avoid modification during iteration
            try:
                await connection.send_json(message)
            except Exception:
                # Remove broken connections
                await self.disconnect_safe(connection)

    async def disconnect_safe(self, websocket: WebSocket):
        """Safely disconnect a websocket."""
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

manager = ConnectionManager()

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Outputs directory - dentro del test-service
SERVICE_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = SERVICE_ROOT / "outputs"
TTS_OUTPUTS_DIR = OUTPUTS_DIR / "tts"
TTS_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Project root for venv
PROJECT_ROOT = SERVICE_ROOT.parent.parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"

# Service configuration
SERVICES = {
    # ── Núcleo (880x) ───────────────────────────────────────────────────────────
    "gateway": {
        "name": "Gateway",
        "port": 8800,
        "health_url": "http://127.0.0.1:8800/health",
        "start_cmd": f'start /B cmd /c "cd services/gateway && "{VENV_PYTHON}" -m uvicorn src.main:app --host 127.0.0.1 --port 8800"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8800 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#4CAF50",
        "manageable": True
    },
    "conversation": {
        "name": "Conversation AI",
        "port": 8801,
        "health_url": "http://127.0.0.1:8801/health",
        "start_cmd": f'start /B cmd /c "cd services/conversation && "{VENV_PYTHON}" -m src.server"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8801 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#2196F3",
        "manageable": True,
        "ui_path": "/conversation-test",
        "requires": ["ollama"]  # Requiere Ollama corriendo
    },
    "assistant": {
        "name": "Assistant",
        "port": 8802,
        "health_url": "http://127.0.0.1:8802/health",
        "start_cmd": None,
        "cwd": str(PROJECT_ROOT),
        "color": "#9C27B0",
        "manageable": False
    },
    "stt": {
        "name": "STT (Speech-to-Text)",
        "port": 8803,
        "health_url": "http://127.0.0.1:8803/health",
        "start_cmd": f'start /B cmd /c "cd services/stt && "{VENV_PYTHON}" -m uvicorn src.server:app --host 127.0.0.1 --port 8803"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8803 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#00BCD4",
        "manageable": True,
        "ui_path": "/stt-test"
    },
    "face": {
        "name": "Face Service 2D (VTuber Avatar)",
        "port": 8804,
        "health_url": "http://127.0.0.1:8804/health",
        "start_cmd": f'start "VTuber Face" cmd /c "cd /D services\\face-service-2D-simple && "{VENV_PYTHON}" run_gui.py"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8804 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#FF5722",
        "manageable": True,
        "requires": ["gateway"],
        "service_type": "GUI"
    },
    "tts-blips": {
        "name": "TTS Blips (Dialogue)",
        "port": 8805,
        "health_url": "http://127.0.0.1:8805/health",
        "start_cmd": f'start /B cmd /c "cd /D services\\tts-blips && "{VENV_PYTHON}" -m src.server"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8805 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#E91E63",
        "manageable": True,
        "ui_path": "/blips-test"
    },
    "tts": {
        "name": "TTS Service",
        "port": 8806,
        "health_url": "http://127.0.0.1:8806/health",
        "start_cmd": f'start /B cmd /c "cd services/tts && "{VENV_PYTHON}" -m uvicorn src.server:app --host 127.0.0.1 --port 8806"',
        "stop_cmd": 'powershell -Command "Get-NetTCPConnection -LocalPort 8806 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
        "cwd": str(PROJECT_ROOT),
        "color": "#FF9800",
        "manageable": True,
        "requires": ["fish"]
    },

    # ── TTS Stack (881x) ────────────────────────────────────────────────────────
    "tts-router": {
        "name": "TTS Router (enrutador central)",
        "port": 8810,
        "health_url": "http://127.0.0.1:8810/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-router" && '
            f'"{VENV_PYTHON}" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8810 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#F57C00",
        "manageable": True,
        "description": "Enrutador TTS – recibe /synthesize y delega al backend según el modo seleccionado."
    },
    "tts-casiopy": {
        "name": "TTS Casiopy FT (voz principal · DEFAULT)",
        "port": 8815,
        "health_url": "http://127.0.0.1:8815/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-casiopy" && '
            f'"{PROJECT_ROOT}\\services\\tts-openvoice\\venv\\Scripts\\python.exe" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8815 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#E91E8C",
        "manageable": True,
        "description": "MeloTTS fine-tuneado (casiopy) – voz principal del proyecto. RTF ~1.5. Sin ToneColorConverter."
    },
    "tts-openvoice": {
        "name": "TTS OpenVoice V2 (streaming rápido)",
        "port": 8811,
        "health_url": "http://127.0.0.1:8811/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-openvoice" && '
            f'"{PROJECT_ROOT}\\services\\tts-openvoice\\venv\\Scripts\\python.exe" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8811 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#43A047",
        "manageable": True,
        "description": "OpenVoice V2 – MeloTTS ES + ToneColorConverter. RTF ~0.2. Uso: streaming."
    },
    "tts-cosyvoice": {
        "name": "TTS CosyVoice3 (streaming calidad)",
        "port": 8812,
        "health_url": "http://127.0.0.1:8812/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-cosyvoice" && '
            f'"{PROJECT_ROOT}\\services\\tts-cosyvoice\\venv\\Scripts\\python.exe" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8812 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#00897B",
        "manageable": True,
        "description": "CosyVoice3-0.5B – Zero-shot / Cross-lingual. RTF ~1.4. Uso: streaming ocasiones especiales."
    },
    "tts-qwen3": {
        "name": "TTS Qwen3-TTS (creación contenido)",
        "port": 8813,
        "health_url": "http://127.0.0.1:8813/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-qwen3" && '
            f'"{PROJECT_ROOT}\\services\\tts-qwen3\\venv\\Scripts\\python.exe" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8813 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#7B1FA2",
        "manageable": True,
        "description": "Qwen3-TTS-12Hz-0.6B – LLM-based AR TTS. RTF ~5. Uso: datasets / contenido."
    },
    "tts-fish": {
        "name": "TTS Fish Speech Local (creación contenido)",
        "port": 8814,
        "health_url": "http://127.0.0.1:8814/health",
        "start_cmd": (
            f'start /B cmd /c "cd /D "{PROJECT_ROOT}\\services\\tts-fish" && '
            f'"{PROJECT_ROOT}\\services\\tts-fish\\venv\\Scripts\\python.exe" server.py"'
        ),
        "stop_cmd": (
            'powershell -Command "Get-NetTCPConnection -LocalPort 8814 -ErrorAction SilentlyContinue'
            ' | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        ),
        "cwd": str(PROJECT_ROOT),
        "color": "#1565C0",
        "manageable": True,
        "description": "Fish Speech openaudio-s1-mini – Llama + VQ-GAN. RTF ~2.2. Uso: datasets / contenido."
    },

    # ── Externos ────────────────────────────────────────────────────────────────
    "ollama": {
        "name": "Ollama (LLM Server)",
        "port": 11434,
        "health_url": "http://127.0.0.1:11434/",
        "cwd": str(PROJECT_ROOT),
        "color": "#673AB7",
        "manageable": False,
        "external": True
    },
    "fish": {
        "name": "Fish Audio Server (Docker)",
        "port": 8080,
        "health_url": "http://127.0.0.1:8080/v1/health",
        "cwd": str(PROJECT_ROOT),
        "color": "#00BCD4",
        "manageable": False,
        "managed_by": "docker"
    },
}


class ServiceStatus(BaseModel):
    name: str
    port: int
    status: str  # "online" | "offline" | "error"
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    color: str
    manageable: bool = False
    requires: Optional[List[str]] = None
    managed_by: Optional[str] = None  # "docker" | None
    ui_path: Optional[str] = None  # Path to UI page if service has one
    external: bool = False  # True if external service (like Ollama)
    service_type: Optional[str] = None  # "GUI" | "HTTP" | None


async def check_service_health(service_id: str, config: dict) -> ServiceStatus:
    """Check health of a single service and update monitoring metrics."""
    # Register service if not already registered
    monitoring.register_service(service_id, config["name"])

    try:
        start_time = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(config["health_url"])
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000

            if response.status_code == 200:
                # Update monitoring
                monitoring.update_service(service_id, ServiceState.ONLINE, response_time)

                return ServiceStatus(
                    name=config["name"],
                    port=config["port"],
                    status="online",
                    response_time_ms=round(response_time, 2),
                    color=config["color"],
                    manageable=config.get("manageable", False),
                    requires=config.get("requires"),
                    managed_by=config.get("managed_by"),
                    ui_path=config.get("ui_path"),
                    external=config.get("external", False),
                    service_type=config.get("service_type")
                )
            else:
                # Update monitoring
                monitoring.update_service(service_id, ServiceState.ERROR, response_time, f"HTTP {response.status_code}")

                return ServiceStatus(
                    name=config["name"],
                    port=config["port"],
                    status="error",
                    error=f"HTTP {response.status_code}",
                    color=config["color"],
                    manageable=config.get("manageable", False),
                    requires=config.get("requires"),
                    managed_by=config.get("managed_by"),
                    ui_path=config.get("ui_path"),
                    external=config.get("external", False),
                    service_type=config.get("service_type")
                )
    except httpx.ConnectError:
        # Update monitoring
        monitoring.update_service(service_id, ServiceState.OFFLINE, error="Connection refused")

        return ServiceStatus(
            name=config["name"],
            port=config["port"],
            status="offline",
            error="Connection refused",
            color=config["color"],
            manageable=config.get("manageable", False),
            requires=config.get("requires"),
            managed_by=config.get("managed_by"),
            ui_path=config.get("ui_path"),
            external=config.get("external", False),
            service_type=config.get("service_type")
        )
    except httpx.TimeoutException:
        # Update monitoring
        monitoring.update_service(service_id, ServiceState.ERROR, error="Timeout (>3s)")

        return ServiceStatus(
            name=config["name"],
            port=config["port"],
            status="error",
            error="Timeout (>3s)",
            color=config["color"],
            manageable=config.get("manageable", False),
            requires=config.get("requires"),
            managed_by=config.get("managed_by"),
            ui_path=config.get("ui_path"),
            external=config.get("external", False),
            service_type=config.get("service_type")
        )
    except Exception as e:
        # Update monitoring
        monitoring.update_service(service_id, ServiceState.ERROR, error=str(e))

        return ServiceStatus(
            name=config["name"],
            port=config["port"],
            status="error",
            error=str(e),
            color=config["color"],
            manageable=config.get("manageable", False),
            requires=config.get("requires"),
            managed_by=config.get("managed_by"),
            ui_path=config.get("ui_path"),
            external=config.get("external", False),
            service_type=config.get("service_type")
        )


@app.get("/")
async def root():
    """Redirect to the monitoring dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/monitoring")


@app.get("/tts")
async def tts_page():
    """Serve the TTS testing page."""
    return FileResponse(STATIC_DIR / "tts.html")


@app.get("/blips-test")
async def blips_test_page():
    """Serve the TTS Blips testing page."""
    return FileResponse(STATIC_DIR / "blips.html")


@app.get("/conversation-test")
async def conversation_test_page():
    """Serve the Conversation AI testing page."""
    return FileResponse(STATIC_DIR / "conversation.html")


@app.get("/vtuber-chat")
async def vtuber_chat_page():
    """Serve the VTuber chat page (integrated with Face Service)."""
    return FileResponse(STATIC_DIR / "vtuber-chat.html")


@app.get("/tts-backends")
async def tts_backends_page():
    """Serve the TTS backends control & testing page."""
    return FileResponse(STATIC_DIR / "tts-backends.html")


@app.get("/monitoring")
async def monitoring_page():
    """Serve the advanced monitoring page."""
    return FileResponse(STATIC_DIR / "monitoring.html")


@app.get("/logs")
async def logs_page():
    """Serve the logs and audit page."""
    return FileResponse(STATIC_DIR / "logs.html")


@app.get("/api/services/status")
async def get_services_status() -> Dict[str, ServiceStatus]:
    """Get health status of all services."""
    tasks = {
        service_id: check_service_health(service_id, config)
        for service_id, config in SERVICES.items()
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    status_map = {}
    for service_id, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            status_map[service_id] = ServiceStatus(
                name=SERVICES[service_id]["name"],
                port=SERVICES[service_id]["port"],
                status="error",
                error=str(result),
                color=SERVICES[service_id]["color"]
            )
        else:
            status_map[service_id] = result

    return status_map


@app.get("/api/tts/emotions")
async def get_tts_emotions():
    """Proxy to TTS emotions endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:8802/emotions")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="TTS service error")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="TTS service offline")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/synthesize")
async def synthesize_tts(text: str, emotion: str = "neutral", save: bool = True):
    """Proxy to TTS synthesize endpoint and optionally save to outputs directory."""
    start_time = time.time()
    filename = None
    audio_size_kb = 0

    # Calculate dynamic timeout based on text length
    # ~4 seconds per word, minimum 30s, maximum 600s (10 min)
    word_count = len(text.split())
    dynamic_timeout = max(30.0, min(600.0, word_count * 4.0))

    try:
        async with httpx.AsyncClient(timeout=dynamic_timeout) as client:
            response = await client.post(
                "http://127.0.0.1:8802/synthesize",
                json={"text": text, "emotion": emotion, "backend": "http"}
            )
            if response.status_code == 200:
                data = response.json()
                duration_ms = (time.time() - start_time) * 1000

                # Save to centralized outputs if requested
                if save and "audio_b64" in data:
                    # Generate filename with timestamp and ID
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_id = abs(hash(text + emotion)) % 10000
                    filename = f"tts_{timestamp}_{file_id}_{emotion}.wav"
                    filepath = TTS_OUTPUTS_DIR / filename

                    # Decode and save
                    audio_bytes = base64.b64decode(data["audio_b64"])
                    filepath.write_bytes(audio_bytes)
                    audio_size_kb = len(audio_bytes) / 1024

                    # Add filepath to response
                    data["saved_to"] = str(filepath)
                    data["filename"] = filename
                    data["generation_time_ms"] = round(duration_ms, 2)

                # Log the synthesis
                audit_logger.log_tts_synthesis(
                    text=text,
                    emotion=emotion,
                    duration_ms=duration_ms,
                    audio_size_kb=audio_size_kb,
                    filename=filename or "not_saved",
                    success=True
                )

                return data
            else:
                duration_ms = (time.time() - start_time) * 1000
                audit_logger.log_tts_synthesis(
                    text=text,
                    emotion=emotion,
                    duration_ms=duration_ms,
                    audio_size_kb=0,
                    filename="failed",
                    success=False,
                    error=f"HTTP {response.status_code}"
                )
                raise HTTPException(status_code=response.status_code, detail="TTS synthesis failed")
    except httpx.ConnectError as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_tts_synthesis(
            text=text,
            emotion=emotion,
            duration_ms=duration_ms,
            audio_size_kb=0,
            filename="failed",
            success=False,
            error="TTS service offline"
        )
        raise HTTPException(status_code=503, detail="TTS service offline")
    except httpx.TimeoutException as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_tts_synthesis(
            text=text,
            emotion=emotion,
            duration_ms=duration_ms,
            audio_size_kb=0,
            filename="failed",
            success=False,
            error="Timeout"
        )
        raise HTTPException(status_code=504, detail="TTS synthesis timeout")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_tts_synthesis(
            text=text,
            emotion=emotion,
            duration_ms=duration_ms,
            audio_size_kb=0,
            filename="failed",
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# Mapping service_id → tts-router mode.
# All TTS backend synthesis requests are routed through the router (port 8810)
# so the router is always the single synthesis entry point in the application.
_ROUTER_MODES: Dict[str, str] = {
    "tts-casiopy":   "casiopy",
    "tts-openvoice": "stream_fast",
    "tts-cosyvoice": "stream_quality",
    "tts-qwen3":     "content",
    "tts-fish":      "content_fish",
}

_ROUTER_URL = "http://127.0.0.1:8810"


@app.post("/api/services/{service_id}/synthesize")
async def proxy_backend_synthesize(service_id: str, request: Request):
    """Proxy a synthesis request for a TTS backend.

    For TTS backends managed by tts-router the request is always forwarded
    to the router (port 8810), keeping it as the single synthesis entry point.
    Other services are contacted directly on their own port.
    """
    svc = SERVICES.get(service_id)
    if not svc:
        raise HTTPException(404, detail=f"Service '{service_id}' not found")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"Invalid JSON body: {e}")

    timeout = 120.0

    router_mode = _ROUTER_MODES.get(service_id)
    if router_mode:
        body["mode"] = router_mode
        target_url = f"{_ROUTER_URL}/synthesize"
        error_hint = (
            f"Asegúrate de que el TTS Router esté activo (puerto 8810) "
            f"antes de sintetizar con '{service_id}'."
        )
    else:
        port = svc.get("port")
        if not port:
            raise HTTPException(400, detail=f"Service '{service_id}' has no port configured")
        target_url = f"http://127.0.0.1:{port}/synthesize"
        error_hint = f"Verifica que el servicio '{service_id}' esté activo (puerto {port})."

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(target_url, json=body)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        raise HTTPException(503, detail=f"No se pudo conectar al destino de síntesis. {error_hint}")
    except httpx.TimeoutException:
        raise HTTPException(504, detail=f"Timeout tras {timeout}s. {error_hint}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/services/{service_id}/start")
async def start_service(service_id: str):
    """Start a service."""
    start_time = time.time()

    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    service = SERVICES[service_id]

    if not service.get("manageable", False):
        raise HTTPException(status_code=400, detail=f"Service '{service_id}' is not manageable")

    if not service.get("start_cmd"):
        raise HTTPException(status_code=400, detail=f"Service '{service_id}' has no start command")

    # Check if service is already running
    try:
        current_status = await check_service_health(service_id, service)
        if current_status.status == "online":
            # Service is already running, no need to start again
            return {
                "ok": True,
                "service": service_id,
                "message": "Service is already running",
                "output": "Service was already active",
                "duration_ms": (time.time() - start_time) * 1000
            }
    except Exception:
        # Service is not running, proceed to start it
        pass

    # Check if service requires other services
    if "requires" in service:
        for req_service in service["requires"]:
            req_status = await check_service_health(req_service, SERVICES[req_service])
            if req_status.status != "online":
                raise HTTPException(
                    status_code=400,
                    detail=f"Service '{service_id}' requires '{req_service}' to be running first"
                )

    try:
        # Execute start command
        # If command contains 'start /B' (Windows background) or 'start "title"' (GUI), don't wait for completion
        cmd = service["start_cmd"]
        is_background = ("start /B" in cmd) or ("start /b" in cmd) or cmd.startswith("cmd /c") or (cmd.startswith("start ") and '"' in cmd[:20])

        if is_background:
            # Start process in background and don't wait
            subprocess.Popen(
                service["start_cmd"],
                shell=True,
                cwd=service.get("cwd"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Wait longer for background service to initialize
            await asyncio.sleep(5)
            result_output = "Service started in background"
        else:
            # Run command and wait for completion (non-blocking via executor)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: subprocess.run(
                service["start_cmd"],
                shell=True,
                cwd=service.get("cwd"),
                capture_output=True,
                text=True,
                timeout=30
            ))
            await asyncio.sleep(2)
            result_output = result.stdout[:500] if result.stdout else None

        # Check if it's actually running
        status = await check_service_health(service_id, service)
        duration_ms = (time.time() - start_time) * 1000

        # Log the action
        audit_logger.log_service_action(
            service_id=service_id,
            action="start",
            duration_ms=duration_ms,
            success=status.status == "online",
            final_status=status.status,
            port=service["port"]
        )

        return {
            "ok": True,
            "service": service_id,
            "action": "start",
            "status": status.status,
            "output": result_output
        }
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="start",
            duration_ms=duration_ms,
            success=False,
            error="Start command timeout"
        )
        raise HTTPException(status_code=504, detail="Start command timeout")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="start",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to start service: {str(e)}")


@app.post("/api/services/{service_id}/stop")
async def stop_service(service_id: str):
    """Stop a service."""
    start_time = time.time()

    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    service = SERVICES[service_id]

    if not service.get("manageable", False):
        raise HTTPException(status_code=400, detail=f"Service '{service_id}' is not manageable")

    try:
        loop = asyncio.get_running_loop()
        if service.get("stop_cmd"):
            await loop.run_in_executor(None, lambda: subprocess.run(
                service["stop_cmd"],
                shell=True,
                cwd=service.get("cwd"),
                capture_output=True,
                text=True,
                timeout=15
            ))
        else:
            # Fallback: kill by port via PowerShell
            port = service["port"]
            await loop.run_in_executor(None, lambda: subprocess.run(
                f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"',
                shell=True,
                capture_output=True,
                timeout=15
            ))

        await asyncio.sleep(3)

        # Check if it stopped
        status = await check_service_health(service_id, service)
        duration_ms = (time.time() - start_time) * 1000

        # Log the action
        audit_logger.log_service_action(
            service_id=service_id,
            action="stop",
            duration_ms=duration_ms,
            success=status.status == "offline",
            final_status=status.status,
            port=service["port"]
        )

        return {
            "ok": True,
            "service": service_id,
            "action": "stop",
            "status": status.status
        }
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="stop",
            duration_ms=duration_ms,
            success=False,
            error="Stop command timeout"
        )
        raise HTTPException(status_code=504, detail="Stop command timeout")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="stop",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {str(e)}")


@app.get("/api/outputs/tts")
async def list_tts_outputs():
    """List all TTS output files."""
    try:
        files = []
        for filepath in sorted(TTS_OUTPUTS_DIR.glob("*.wav"), reverse=True):
            stat = filepath.stat()
            files.append({
                "filename": filepath.name,
                "size_kb": round(stat.st_size / 1024, 2),
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "path": str(filepath)
            })

        return {
            "ok": True,
            "count": len(files),
            "files": files[:50]  # Limit to 50 most recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/outputs/tts/{filename}")
async def download_tts_output(filename: str):
    """Download a TTS output file."""
    filepath = TTS_OUTPUTS_DIR / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(filepath),
        media_type="audio/wav",
        filename=filename
    )


@app.get("/api/logs/recent")
async def get_recent_logs(limit: int = 50):
    """Get recent audit logs from memory buffer."""
    try:
        logs = audit_logger.get_recent_logs(limit=limit)
        return {
            "ok": True,
            "count": len(logs),
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/tts-metrics")
async def get_tts_metrics():
    """Get TTS synthesis metrics summary."""
    try:
        metrics = audit_logger.get_tts_metrics()
        return {
            "ok": True,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/service/{service_id}")
async def get_service_logs(service_id: str, limit: int = 50):
    """Get recent logs for a specific service."""
    try:
        all_logs = audit_logger.get_recent_logs(limit=200)

        # Filter logs by service_id
        # Logs are stored with action = "{action}_{service_id}" (e.g., "start_tts", "stop_docker")
        service_logs = []
        for log in all_logs:
            action = log.get("action", "")
            event_type = log.get("event_type", "")

            # Check if this log is related to the service
            if (action.endswith(f"_{service_id}") or
                action == service_id or
                service_id in action.lower()):
                service_logs.append(log)

        # Limit results
        service_logs = service_logs[:limit]

        return {
            "ok": True,
            "service_id": service_id,
            "count": len(service_logs),
            "logs": service_logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/summary")
async def get_logs_summary():
    """Get overall logs summary."""
    try:
        logs = audit_logger.get_recent_logs(limit=100)

        # Count by event type
        event_counts = {}
        success_count = 0
        error_count = 0

        for log in logs:
            event_type = log.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

            if log.get("success"):
                success_count += 1
            else:
                error_count += 1

        return {
            "ok": True,
            "total_events": len(logs),
            "success_count": success_count,
            "error_count": error_count,
            "event_types": event_counts,
            "recent_logs": logs[:10]  # Last 10 for quick view
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check for test service itself."""
    return {"ok": True, "status": "alive", "service": "test-dashboard"}


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.websocket("/ws/monitoring")
async def websocket_monitoring(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring updates."""
    await manager.connect(websocket)
    try:
        # Send initial data
        services_status = await get_services_status()
        # Convert Pydantic models to dicts for JSON serialization
        services_dict = {sid: svc.model_dump() for sid, svc in services_status.items()}

        await websocket.send_json({
            "type": "init",
            "services": services_dict,
            "metrics": monitoring.get_all_metrics(),
            "health": monitoring.get_system_health()
        })

        # Keep connection alive and send periodic updates
        last_update = asyncio.get_event_loop().time()
        while True:
            try:
                # Wait for message or timeout (client ping/pong)
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                # Check if we should send a full update (every 10 seconds)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update >= 10.0:
                    # Send full update with metrics
                    services_status = await get_services_status()
                    services_dict = {sid: svc.model_dump() for sid, svc in services_status.items()}

                    await websocket.send_json({
                        "type": "update",
                        "services": services_dict,
                        "metrics": monitoring.get_all_metrics(),
                        "health": monitoring.get_system_health()
                    })
                    last_update = current_time
                else:
                    # Just send heartbeat
                    await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)


@app.get("/api/monitoring/metrics")
async def get_monitoring_metrics():
    """Get detailed monitoring metrics for all services."""
    return {
        "ok": True,
        "metrics": monitoring.get_all_metrics(),
        "system_health": monitoring.get_system_health()
    }


@app.get("/api/monitoring/metrics/{service_id}")
async def get_service_monitoring_metrics(service_id: str):
    """Get detailed metrics for a specific service."""
    metrics = monitoring.get_service_metrics(service_id)
    if metrics:
        return {"ok": True, "metrics": metrics}
    raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found in monitoring")


@app.get("/api/monitoring/alerts")
async def get_monitoring_alerts(limit: int = 20, unresolved_only: bool = False):
    """Get recent monitoring alerts."""
    return {
        "ok": True,
        "alerts": monitoring.get_recent_alerts(limit=limit, unresolved_only=unresolved_only)
    }


@app.get("/api/monitoring/system-health")
async def get_system_health_endpoint():
    """Get overall system health summary."""
    return {
        "ok": True,
        "health": monitoring.get_system_health()
    }


@app.get("/api/docker/status")
async def get_docker_status(container_name: str = "fish-speech-ngc"):
    """Get Docker container status."""
    status = await DockerMonitor.check_container_status(container_name)
    return {"ok": True, "container": container_name, **status}


@app.get("/api/docker/stats")
async def get_docker_stats_endpoint(container_name: str = "fish-speech-ngc"):
    """Get Docker container resource usage stats."""
    stats = await DockerMonitor.get_container_stats(container_name)
    return {"ok": True, "container": container_name, "stats": stats}


@app.get("/api/gpu/stats")
async def get_gpu_stats_endpoint():
    """Get GPU statistics via nvidia-smi."""
    stats = await DockerMonitor.get_gpu_stats()
    return {"ok": True, "gpu": stats}


# ============================================================================
# DOCKER CONTROL ENDPOINTS
# ============================================================================

@app.post("/api/docker/start")
async def start_docker_container(container_name: str = "fish-speech-ngc"):
    """Start Fish Speech Docker container."""
    start_time = time.time()

    try:
        # Start container using docker-compose
        result = subprocess.run(
            f'cd services/tts/docker-ngc && docker-compose up -d',
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )

        await asyncio.sleep(3)  # Wait for container to start

        # Check status
        status = await DockerMonitor.check_container_status(container_name)
        duration_ms = (time.time() - start_time) * 1000

        audit_logger.log_service_action(
            service_id="docker-fish",
            action="start",
            duration_ms=duration_ms,
            success=status.get("running", False),
            final_status="running" if status.get("running") else "stopped"
        )

        return {
            "ok": True,
            "container": container_name,
            "action": "start",
            "running": status.get("running", False),
            "output": result.stdout[:500] if result.stdout else None
        }
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="start",
            duration_ms=duration_ms,
            success=False,
            error="Start command timeout"
        )
        raise HTTPException(status_code=504, detail="Docker start timeout")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="start",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to start Docker: {str(e)}")


@app.post("/api/docker/stop")
async def stop_docker_container(container_name: str = "fish-speech-ngc"):
    """Stop Fish Speech Docker container (without removing it)."""
    start_time = time.time()

    try:
        result = subprocess.run(
            f'cd services/tts/docker-ngc && docker-compose stop',
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )

        await asyncio.sleep(2)  # Wait for container to stop

        # Check status
        status = await DockerMonitor.check_container_status(container_name)
        duration_ms = (time.time() - start_time) * 1000

        audit_logger.log_service_action(
            service_id="docker-fish",
            action="stop",
            duration_ms=duration_ms,
            success=not status.get("running", True),
            final_status="stopped" if not status.get("running") else "running"
        )

        return {
            "ok": True,
            "container": container_name,
            "action": "stop",
            "running": status.get("running", False),
            "output": result.stdout[:500] if result.stdout else None
        }
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="stop",
            duration_ms=duration_ms,
            success=False,
            error="Stop command timeout"
        )
        raise HTTPException(status_code=504, detail="Docker stop timeout")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="stop",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to stop Docker: {str(e)}")


@app.post("/api/docker/restart")
async def restart_docker_container(container_name: str = "fish-speech-ngc"):
    """Restart Fish Speech Docker container."""
    start_time = time.time()

    try:
        # Stop first
        await stop_docker_container(container_name)
        await asyncio.sleep(2)

        # Then start
        result = await start_docker_container(container_name)

        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="restart",
            duration_ms=duration_ms,
            success=result.get("running", False),
            final_status="running" if result.get("running") else "stopped"
        )

        return {
            "ok": True,
            "container": container_name,
            "action": "restart",
            "running": result.get("running", False)
        }
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="restart",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to restart Docker: {str(e)}")


@app.post("/api/docker/remove")
async def remove_docker_container(container_name: str = "fish-speech-ngc", confirm: bool = False):
    """Remove Fish Speech Docker container (DESTRUCTIVE - requires confirmation)."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Container removal requires confirmation. Add '?confirm=true' to proceed."
        )

    start_time = time.time()

    try:
        result = subprocess.run(
            f'cd services/tts/docker-ngc && docker-compose down',
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )

        await asyncio.sleep(2)  # Wait for container to be removed

        # Check status
        status = await DockerMonitor.check_container_status(container_name)
        duration_ms = (time.time() - start_time) * 1000

        audit_logger.log_service_action(
            service_id="docker-fish",
            action="remove",
            duration_ms=duration_ms,
            success=not status.get("exists", True),
            final_status="removed" if not status.get("exists") else "exists"
        )

        return {
            "ok": True,
            "container": container_name,
            "action": "remove",
            "exists": status.get("exists", False),
            "output": result.stdout[:500] if result.stdout else None
        }
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="remove",
            duration_ms=duration_ms,
            success=False,
            error="Timeout"
        )
        raise HTTPException(status_code=504, detail="Docker remove operation timed out")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id="docker-fish",
            action="remove",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to remove Docker: {str(e)}")


# ============================================================================
# SERVICE RESTART ENDPOINT
# ============================================================================

@app.post("/api/services/{service_id}/restart")
async def restart_service(service_id: str):
    """Restart a service (stop then start)."""
    start_time = time.time()

    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    service = SERVICES[service_id]

    if not service.get("manageable", False):
        raise HTTPException(status_code=400, detail=f"Service '{service_id}' is not manageable")

    try:
        # Try to stop first (may fail if not running, that's ok)
        try:
            await stop_service(service_id)
        except:
            pass  # Ignore stop errors

        await asyncio.sleep(2)

        # Start the service
        start_result = await start_service(service_id)

        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="restart",
            duration_ms=duration_ms,
            success=start_result.get("status") == "online",
            final_status=start_result.get("status", "unknown"),
            port=service["port"]
        )

        return {
            "ok": True,
            "service": service_id,
            "action": "restart",
            "status": start_result.get("status")
        }
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log_service_action(
            service_id=service_id,
            action="restart",
            duration_ms=duration_ms,
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {str(e)}")


@app.get("/api/monitoring/full-report")
async def get_full_monitoring_report():
    """Get comprehensive monitoring report with all data."""
    # Get all service statuses
    services_status = await get_services_status()

    # Get Docker status
    docker_status = await DockerMonitor.check_container_status()
    docker_stats = await DockerMonitor.get_container_stats()

    # Get GPU stats
    gpu_stats = await DockerMonitor.get_gpu_stats()

    return {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "system_health": monitoring.get_system_health(),
        "services": services_status,
        "metrics": monitoring.get_all_metrics(),
        "alerts": monitoring.get_recent_alerts(limit=10, unresolved_only=True),
        "docker": {
            "status": docker_status,
            "stats": docker_stats
        },
        "gpu": gpu_stats
    }


# Background task for broadcasting updates
async def broadcast_monitoring_updates():
    """Periodically broadcast monitoring updates to connected WebSocket clients."""
    while True:
        await asyncio.sleep(5)  # Update every 5 seconds

        if manager.active_connections:
            # Get fresh data
            services_status = await get_services_status()
            metrics = monitoring.get_all_metrics()
            health = monitoring.get_system_health()
            alerts = monitoring.get_recent_alerts(limit=5, unresolved_only=True)

            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "update",
                "timestamp": datetime.now().isoformat(),
                "services": services_status,
                "metrics": metrics,
                "health": health,
                "alerts": alerts
            })


@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    # Start monitoring broadcast task
    asyncio.create_task(broadcast_monitoring_updates())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8900)
