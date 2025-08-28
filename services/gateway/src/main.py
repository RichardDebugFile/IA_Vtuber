from typing import Dict, Set, Any
import asyncio
import os
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi import Body
from pydantic import BaseModel
from starlette.websockets import WebSocketState

app = FastAPI(title="vtuber-gateway", version="0.1.0")

CONVERSATION_HTTP = os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")
TTS_HTTP = os.getenv("TTS_HTTP", "http://127.0.0.1:8802")

# Suscripciones por tópico
# topic -> set(WebSocket)
SUBS: Dict[str, Set[WebSocket]] = {
    "utterance": set(),
    "emotion": set(),
    "audio": set(),
    "avatar-action": set(),
}

class PublishIn(BaseModel):
    topic: str
    data: Dict[str, Any]


class ChatIn(BaseModel):
    user: str = "local"
    text: str


class ChatOut(BaseModel):
    reply: str
    emotion: str
    audio_b64: str

@app.get("/health")
async def health():
    return {"ok": True, "topics": list(SUBS.keys())}

async def _broadcast(topic: str, data: Dict[str, Any]) -> int:
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

    total = len(SUBS[topic])
    for ws in dead:
        for t in SUBS.values():
            t.discard(ws)
    return total - len(dead)


@app.post("/publish")
async def publish(body: PublishIn):
    if body.topic not in SUBS:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{body.topic}'")
    delivered = await _broadcast(body.topic, body.data)
    return {"delivered": delivered}


@app.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn) -> ChatOut:
    # Obtener respuesta y emoción del servicio de conversación
    payload = {"user": body.user, "text": body.text}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{CONVERSATION_HTTP}/chat", json=payload)
        resp.raise_for_status()
        conv_data = resp.json()
    reply = conv_data.get("reply", "")
    emotion = conv_data.get("emotion", "neutral")

    # Generar audio usando el servicio TTS
    tts_payload = {"text": reply, "emotion": emotion}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{TTS_HTTP}/synthesize", json=tts_payload)
        resp.raise_for_status()
        tts_data = resp.json()
    audio_b64 = tts_data.get("audio_b64", "")

    await asyncio.gather(
        _broadcast("utterance", {"text": reply}),
        _broadcast("emotion", {"label": emotion}),
        _broadcast("audio", {"audio_b64": audio_b64}),
    )

    return ChatOut(reply=reply, emotion=emotion, audio_b64=audio_b64)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    # Suscripciones activas de esta conexión
    my_topics: Set[str] = set()
    try:
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                continue
            t = msg.get("type")
            if t == "subscribe":
                topics = msg.get("topics") or []
                # quitar suscripciones anteriores
                for tp in list(my_topics):
                    SUBS.get(tp, set()).discard(ws)
                my_topics.clear()
                # agregar nuevas
                for tp in topics:
                    if tp in SUBS:
                        SUBS[tp].add(ws)
                        my_topics.add(tp)
                # opcional: confirmar
                await ws.send_json({"type": "subscribed", "topics": list(my_topics)})

            elif t == "ping":
                await ws.send_json({"type": "pong"})
            # puedes añadir "unsubscribe", etc.

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # limpiar suscripciones de esta conexión
        for tp in my_topics:
            SUBS.get(tp, set()).discard(ws)
