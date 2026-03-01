"""
gateway v2.0 — Hub central de Casiopy VTuber.

Responsabilidades:
  1. Pub/Sub WebSocket en tiempo real (topics: utterance, emotion,
     avatar-action, audio, service-status).
  2. POST /orchestrate/chat  → orquesta conversation + TTS + publica al bus.
  3. POST /orchestrate/stt   → proxy a stt-service para transcripción.
  4. GET/POST /services/*    → proxy a monitoring-service con notificaciones WS.

Todos los clientes (casiopy-app, face-service-2D-simple, etc.) solo necesitan
conocer la URL del gateway.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Set

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketState

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

app = FastAPI(title="vtuber-gateway", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── URLs de servicios downstream ───────────────────────────────────────────────
CONVERSATION_URL = os.getenv("CONVERSATION_URL", "http://127.0.0.1:8801")
TTS_ROUTER_URL   = os.getenv("TTS_ROUTER_URL",   "http://127.0.0.1:8810")
TTS_BLIPS_URL    = os.getenv("TTS_BLIPS_URL",     "http://127.0.0.1:8805")
STT_URL          = os.getenv("STT_URL",           "http://127.0.0.1:8803")
MONITORING_URL   = os.getenv("MONITORING_URL",    "http://127.0.0.1:8900")

# ── Registro pub/sub ──────────────────────────────────────────────────────────
VALID_TOPICS: set[str] = {
    "utterance",
    "emotion",
    "avatar-action",
    "audio",
    "service-status",   # notificaciones de arranque/parada de servicios
}
SUBS: Dict[str, Set[WebSocket]] = {t: set() for t in VALID_TOPICS}


# ══════════════════════════════════════════════════════════════════════════════
# Modelos Pydantic
# ══════════════════════════════════════════════════════════════════════════════

class PublishIn(BaseModel):
    topic: str
    data: Dict[str, Any]


class ChatRequest(BaseModel):
    text: str
    user_id: str = "casiopy-app"
    tts_mode: str = Field(
        default="casiopy",
        description="Modo TTS: 'casiopy' (voz fine-tuned, default) | "
                    "'stream_fast' (OpenVoice V2, RTF~0.74) | 'blips' (síntesis aditiva, fallback)",
    )


class ChatResponse(BaseModel):
    reply: str
    emotion: str
    audio_b64: Optional[str] = None
    turn: int = 0
    tts_backend_used: Optional[str] = None
    memories_used: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# Helper: difusión al bus
# ══════════════════════════════════════════════════════════════════════════════

async def _broadcast(topic: str, data: dict) -> int:
    """
    Difunde un evento a todos los suscriptores del tópico.
    Limpia automáticamente sockets desconectados.
    Retorna el número de mensajes entregados.
    """
    if topic not in SUBS:
        return 0
    payload = {"type": topic, "data": data}
    dead: Set[WebSocket] = set()
    for ws in list(SUBS[topic]):
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.send_json(payload)
            else:
                dead.add(ws)
        except Exception:
            dead.add(ws)
    # Limpiar sockets muertos de todos los tópicos
    for ws in dead:
        for subs_set in SUBS.values():
            subs_set.discard(ws)
    return len(SUBS[topic])


# ══════════════════════════════════════════════════════════════════════════════
# Helper: TTS con cadena de fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _tts_with_fallback(
    client: httpx.AsyncClient, text: str, emotion: str, tts_mode: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Sintetiza voz con fallback automático.
    Retorna (audio_b64, nombre_backend) o (None, None) si todo falla.

    Cadena de prioridad:
      "casiopy"     → tts-router mode=casiopy → blips
      "stream_fast" → tts-router mode=stream_fast → tts-router mode=casiopy → blips
      "blips"       → tts-blips directo (siempre disponible)
    """
    # ── Blips directo: sin fallback, siempre funciona ─────────────────────────
    if tts_mode == "blips":
        try:
            r = await client.post(
                f"{TTS_BLIPS_URL}/blips/generate",
                json={"text": text, "emotion": emotion},
                timeout=10.0,
            )
            if r.is_success:
                return r.json().get("audio_b64"), "blips"
        except Exception as exc:
            log.warning("[tts] blips directo falló: %s", exc)
        return None, None

    # ── Intentar tts-router: modo solicitado primero, luego casiopy ───────────
    modes_to_try = [tts_mode] + (["casiopy"] if tts_mode != "casiopy" else [])
    for mode in modes_to_try:
        try:
            r = await client.post(
                f"{TTS_ROUTER_URL}/synthesize",
                json={
                    "text":    text,
                    "voice":   "casiopy",
                    "mode":    mode,
                    "emotion": emotion,
                    "speed":   1.0,
                },
                timeout=25.0,
            )
            if r.is_success and r.json().get("ok"):
                label = mode if mode == tts_mode else "casiopy_fallback"
                return r.json().get("audio_b64"), label
        except Exception as exc:
            log.warning("[tts] router modo='%s' falló: %s", mode, exc)

    # ── Fallback final: blips ─────────────────────────────────────────────────
    try:
        r = await client.post(
            f"{TTS_BLIPS_URL}/blips/generate",
            json={"text": text, "emotion": emotion},
            timeout=10.0,
        )
        if r.is_success:
            log.info("[tts] usando blips_fallback")
            return r.json().get("audio_b64"), "blips_fallback"
    except Exception as exc:
        log.warning("[tts] blips_fallback falló: %s", exc)

    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# Helper: proxy a monitoring-service
# ══════════════════════════════════════════════════════════════════════════════

async def _monitoring(method: str, path: str, timeout: float = 30.0) -> dict:
    """
    Llama a monitoring-service y retorna el JSON de respuesta.
    Traduce errores de conexión/timeout a HTTPException.
    """
    url = f"{MONITORING_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await getattr(client, method)(url)
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError:
        raise HTTPException(
            502,
            detail=f"monitoring-service no disponible en {MONITORING_URL}. "
                   "Inicia monitoring-service (puerto 8900) antes de gestionar servicios.",
        )
    except httpx.TimeoutException:
        raise HTTPException(504, detail=f"monitoring-service timeout ({timeout}s)")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(502, detail=f"monitoring-service error inesperado: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints base
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Estado del gateway y estadísticas de suscriptores."""
    return {
        "status": "ok",
        "service": "gateway",
        "version": "2.0.0",
        "topics": sorted(VALID_TOPICS),
        "subscribers": {t: len(s) for t, s in SUBS.items()},
    }


@app.post("/publish")
async def publish(body: PublishIn):
    """Publica un evento a todos los suscriptores del tópico."""
    if body.topic not in VALID_TOPICS:
        raise HTTPException(
            400,
            detail=f"'{body.topic}' is not a valid topic. "
                   f"Valid topics: {sorted(VALID_TOPICS)}",
        )
    delivered = await _broadcast(body.topic, body.data)
    return {"ok": True, "topic": body.topic, "delivered": delivered}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """
    WebSocket pub/sub.
    Mensajes entrantes admitidos:
      {"type": "subscribe",   "topics": [...]}
      {"type": "unsubscribe", "topics": [...]}
      {"type": "ping"}
    Mensajes salientes:
      {"type": "subscribed",     "topics": [...]}
      {"type": "<topic>",        "data":   {...}}   ← eventos
      {"type": "pong"}
    """
    await ws.accept()
    my_topics: Set[str] = set()
    try:
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                continue
            t = msg.get("type")

            if t == "subscribe":
                # Reemplaza suscripciones anteriores
                for tp in list(my_topics):
                    SUBS.get(tp, set()).discard(ws)
                my_topics.clear()
                for tp in msg.get("topics") or []:
                    if tp in SUBS:
                        SUBS[tp].add(ws)
                        my_topics.add(tp)
                await ws.send_json({"type": "subscribed", "topics": list(my_topics)})

            elif t == "unsubscribe":
                for tp in msg.get("topics") or []:
                    SUBS.get(tp, set()).discard(ws)
                    my_topics.discard(tp)

            elif t == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        for tp in my_topics:
            SUBS.get(tp, set()).discard(ws)


# ══════════════════════════════════════════════════════════════════════════════
# Orquestación: Chat completo
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/orchestrate/chat", response_model=ChatResponse)
async def orchestrate_chat(body: ChatRequest):
    """
    Pipeline completo de un turno de conversación:
      1. Llama a conversation-service (LLM + Core Memory + búsqueda semántica).
      2. Sintetiza TTS con cadena de fallback (casiopy → stream_fast → blips).
      3. Publica utterance, emotion y audio al bus WS para otros suscriptores
         (p.ej. face-service-2D-simple actualiza la sprite del avatar).
      4. Retorna el resultado completo al llamador (casiopy-app).

    Degradación graceful:
      - Si TTS falla completamente → responde sin audio (reply + emotion OK).
      - Si conversation falla → HTTP 502.
    """
    async with httpx.AsyncClient() as client:
        # ── 1. Llamar a conversation-service ─────────────────────────────────
        try:
            conv_r = await client.post(
                f"{CONVERSATION_URL}/chat",
                json={"user": body.user_id, "text": body.text},
                timeout=45.0,
            )
            conv_r.raise_for_status()
            conv = conv_r.json()
        except httpx.ConnectError:
            raise HTTPException(
                502,
                detail="conversation-service no disponible (puerto 8801). "
                       "Inicia Ollama y conversation antes de chatear.",
            )
        except httpx.TimeoutException:
            raise HTTPException(504, detail="conversation-service timeout (>45s). El LLM tardó demasiado.")
        except Exception as exc:
            raise HTTPException(502, detail=f"conversation-service error: {exc}")

        reply    = conv.get("reply", "")
        emotion  = conv.get("emotion", "neutral")
        turn     = conv.get("turn", 0)
        memories = conv.get("memories_used", 0)

        # ── 2. TTS con fallback ───────────────────────────────────────────────
        audio_b64, tts_backend = await _tts_with_fallback(
            client, reply, emotion, body.tts_mode
        )

    # ── 3. Publicar al bus de eventos (no bloquea) ───────────────────────────
    await _broadcast("utterance", {"text": reply, "user_id": body.user_id, "turn": turn})
    await _broadcast("emotion",   {"emotion": emotion})
    if audio_b64:
        await _broadcast("audio", {"audio_b64": audio_b64, "tts_backend": tts_backend})

    log.info(
        "[chat] user=%r  emotion=%r  turn=%d  tts=%r  memories=%d",
        body.user_id, emotion, turn, tts_backend, memories,
    )

    return ChatResponse(
        reply=reply,
        emotion=emotion,
        audio_b64=audio_b64,
        turn=turn,
        tts_backend_used=tts_backend,
        memories_used=memories,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Orquestación: STT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/orchestrate/stt")
async def orchestrate_stt(audio: UploadFile = File(...)):
    """
    Proxy a stt-service (puerto 8803) para transcripción de audio.
    Acepta cualquier formato que Faster-Whisper soporte (WebM, WAV, OGG, MP3…).
    Retorna {text, language, duration_s, segments?}.
    """
    try:
        audio_bytes = await audio.read()
    except Exception as exc:
        raise HTTPException(400, detail=f"Error leyendo archivo de audio: {exc}")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                f"{STT_URL}/transcribe",
                files={
                    "audio": (
                        audio.filename or "audio.webm",
                        audio_bytes,
                        audio.content_type or "audio/webm",
                    )
                },
            )
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError:
        raise HTTPException(
            502,
            detail="stt-service no disponible (puerto 8803). "
                   "Activa el STT desde el panel de servicios.",
        )
    except httpx.TimeoutException:
        raise HTTPException(504, detail="stt-service timeout (>90s). Audio demasiado largo.")
    except Exception as exc:
        raise HTTPException(502, detail=f"stt-service error: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Gestión de servicios — proxy a monitoring-service con eventos WS
# ══════════════════════════════════════════════════════════════════════════════
#
# El gateway NO gestiona subprocesos directamente; eso lo hace monitoring-service.
# El gateway añade valor publicando eventos service-status al bus WS para que
# los clientes reciban actualizaciones en tiempo real sin necesidad de polling.

@app.get("/services/status")
async def services_status():
    """
    Estado de todos los servicios registrados en monitoring-service.
    Proxy GET /api/services/status → monitoring:8900.
    """
    return await _monitoring("get", "/api/services/status", timeout=10.0)


@app.get("/services/{service_id}/status")
async def service_status_single(service_id: str):
    """Estado de un servicio específico."""
    all_status = await _monitoring("get", "/api/services/status", timeout=10.0)
    if service_id not in all_status:
        raise HTTPException(404, detail=f"Servicio '{service_id}' no encontrado")
    return {service_id: all_status[service_id]}


@app.post("/services/{service_id}/start")
async def service_start(service_id: str):
    """
    Inicia un servicio vía monitoring-service.
    Publica service-status:{starting, started|start_failed} al bus WS.
    Respeta dependencias (monitoring verifica 'requires' antes de arrancar).
    """
    await _broadcast("service-status", {"id": service_id, "action": "starting"})
    result = await _monitoring("post", f"/api/services/{service_id}/start", timeout=60.0)
    action = "started" if result.get("status") == "online" else "start_failed"
    await _broadcast("service-status", {"id": service_id, "action": action, "detail": result})
    return result


@app.post("/services/{service_id}/stop")
async def service_stop(service_id: str):
    """
    Para un servicio vía monitoring-service.
    Publica service-status:{stopping, stopped} al bus WS.
    """
    await _broadcast("service-status", {"id": service_id, "action": "stopping"})
    result = await _monitoring("post", f"/api/services/{service_id}/stop", timeout=15.0)
    await _broadcast("service-status", {"id": service_id, "action": "stopped", "detail": result})
    return result


@app.post("/services/{service_id}/restart")
async def service_restart(service_id: str):
    """
    Para y vuelve a iniciar un servicio.
    Publica service-status:{restarting, started|restart_failed}.
    """
    await _broadcast("service-status", {"id": service_id, "action": "restarting"})
    # Parar (ignora error si ya estaba parado)
    try:
        await _monitoring("post", f"/api/services/{service_id}/stop", timeout=15.0)
    except HTTPException:
        pass
    # Iniciar
    result = await _monitoring("post", f"/api/services/{service_id}/start", timeout=60.0)
    action = "started" if result.get("status") == "online" else "restart_failed"
    await _broadcast("service-status", {"id": service_id, "action": action, "detail": result})
    return result
