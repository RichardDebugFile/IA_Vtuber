from typing import Dict, Set, Any
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi import Body
from pydantic import BaseModel
from starlette.websockets import WebSocketState

app = FastAPI(title="vtuber-gateway", version="0.1.0")

# Suscripciones por tópico
# topic -> set(WebSocket)
SUBS: Dict[str, Set[WebSocket]] = {
    "utterance": set(),
    "emotion": set(),
    "avatar-action": set(),
}

class PublishIn(BaseModel):
    topic: str
    data: Dict[str, Any]

@app.get("/health")
async def health():
    return {"ok": True, "topics": list(SUBS.keys())}

@app.post("/publish")
async def publish(body: PublishIn):
    topic = body.topic
    if topic not in SUBS:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")

    payload = {"type": topic, "data": body.data}
    dead: Set[WebSocket] = set()

    # Difundir a todos los suscriptores del tópico
    for ws in list(SUBS[topic]):
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.send_json(payload)
            else:
                dead.add(ws)
        except Exception:
            dead.add(ws)

    # limpiar sockets muertos
    for ws in dead:
        for t in SUBS.values():
            t.discard(ws)

    return {"delivered": len(SUBS[topic]) - len(dead)}

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
