import os, asyncio, time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from dotenv import load_dotenv
load_dotenv()

from src.llm_ollama import chat, list_models
from src.emotion import classify
from src.ollama_manager import OllamaManager

# ── Configuración ──────────────────────────────────────────────────────────────
GATEWAY_HTTP  = os.getenv("GATEWAY_HTTP",  "http://127.0.0.1:8800")
OLLAMA_HOST   = os.getenv("OLLAMA_HOST",   "http://127.0.0.1:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",  "gemma3")
MEMORY_HTTP   = os.getenv("MEMORY_HTTP",   "http://127.0.0.1:8820")

_DEFAULT_SYSTEM_PROMPT = (
    "Eres Casiopy, una VTuber con personalidad sarcástica pero cariñosa. "
    "Hablas en español, eres directa y tienes sentido del humor. "
    "Tus respuestas son breves y naturales."
)

# ── Estado de sesiones en memoria ─────────────────────────────────────────────
_MAX_HISTORY_TURNS = 20   # máximo de turnos (user+assistant) por sesión

# { user_id: {"session_id": str, "history": [...], "turn": int} }
_active_sessions: Dict[str, Dict[str, Any]] = {}

# Caché del system prompt de Core Memory (TTL 5 min)
_system_prompt_cache: Optional[str] = None
_system_prompt_ts: float = 0.0
_SYSTEM_PROMPT_TTL: float = 300.0

# Global Ollama manager
ollama_manager: OllamaManager | None = None


# ── Helpers de memoria (degradación graceful) ──────────────────────────────────
async def _memory_post(path: str, body: Dict[str, Any]) -> Optional[Dict]:
    """POST al memory-service. Devuelve None si no está disponible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{MEMORY_HTTP}{path}", json=body)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def _memory_get(path: str) -> Optional[Dict]:
    """GET al memory-service. Devuelve None si no está disponible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MEMORY_HTTP}{path}")
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def _get_system_prompt() -> str:
    """Devuelve el system prompt de Core Memory (cacheado 5 min)."""
    global _system_prompt_cache, _system_prompt_ts

    now = time.monotonic()
    if _system_prompt_cache and (now - _system_prompt_ts) < _SYSTEM_PROMPT_TTL:
        return _system_prompt_cache

    data = await _memory_get("/core-memory/system-prompt/generate")
    if data and "system_prompt" in data:
        _system_prompt_cache = data["system_prompt"]
        _system_prompt_ts = now
        return _system_prompt_cache

    # Fallback: prompt por defecto (memory-service caído o sin datos)
    return _system_prompt_cache or _DEFAULT_SYSTEM_PROMPT


async def _store_interaction(
    session_id: str,
    user_id: str,
    input_text: str,
    output_text: str,
    input_emotion: str,
    output_emotion: str,
    turn: int,
    latency_ms: int,
) -> None:
    """Almacena la interacción en memory-service (fire-and-forget)."""
    await _memory_post("/interactions", {
        "session_id":    session_id,
        "user_id":       user_id,
        "input_text":    input_text,
        "output_text":   output_text,
        "input_emotion": input_emotion,
        "output_emotion": output_emotion,
        "input_method":  "text",
        "conversation_turn": turn,
        "latency_ms":    latency_ms,
        "model_version": OLLAMA_MODEL,
    })


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ollama_manager
    print(f"[CONVERSATION] Checking Ollama at {OLLAMA_HOST}...")
    ollama_manager = OllamaManager(host=OLLAMA_HOST, model=OLLAMA_MODEL)

    ready, message = await ollama_manager.ensure_ready(auto_start=True)
    if ready:
        print(f"[CONVERSATION] [OK] {message}")
    else:
        print(f"[CONVERSATION] [WARN] {message} — service will start but /chat may fail")

    print(f"[CONVERSATION] Memory-service: {MEMORY_HTTP}")
    yield

    ollama_manager = None
    print("[CONVERSATION] Shutdown complete")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="vtuber-conversation", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ────────────────────────────────────────────────────────────────────
class ChatIn(BaseModel):
    user: str = "local"
    text: str

class ChatOut(BaseModel):
    reply: str
    emotion: str
    model: str

class SessionResetIn(BaseModel):
    user: str = "local"


# ── Publicación al gateway ─────────────────────────────────────────────────────
async def publish(topic: str, data: Dict[str, Any]) -> None:
    url = f"{GATEWAY_HTTP}/publish"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json={"topic": topic, "data": data})


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    ollama_ready = False
    if ollama_manager:
        ollama_ready = await ollama_manager.is_server_running()

    mem_ok = (await _memory_get("/health")) is not None

    return {
        "ok": True,
        "ollama_host":  OLLAMA_HOST,
        "model":        OLLAMA_MODEL,
        "ollama_ready": ollama_ready,
        "memory_url":   MEMORY_HTTP,
        "memory_ok":    mem_ok,
        "active_sessions": len(_active_sessions),
    }


@app.get("/models")
async def models():
    try:
        ms = await list_models()
        return {"models": ms}
    except httpx.HTTPError as e:
        return JSONResponse({"error": f"Ollama HTTP error: {e}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"Unexpected: {e}"}, status_code=500)


@app.post("/chat", response_model=ChatOut)
async def chat_endpoint(body: ChatIn):
    user_id = body.user or "local"

    # 1. System prompt (Core Memory o default)
    system_prompt = await _get_system_prompt()

    # 2. Obtener o crear sesión local
    if user_id not in _active_sessions:
        # Crear sesión en memory-service (no bloqueante si falla)
        sess_data = await _memory_post("/sessions", {"user_id": user_id})
        session_id = (sess_data or {}).get("session_id", f"local-{user_id}-{int(time.time())}")
        _active_sessions[user_id] = {
            "session_id": session_id,
            "history":    [],
            "turn":       0,
        }

    sess = _active_sessions[user_id]

    # 3. Construir mensajes: [system] + historial + [nuevo mensaje]
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]
    messages.extend(sess["history"])
    messages.append({"role": "user", "content": body.text})

    # 4. Llamar a Ollama
    t0 = time.monotonic()
    try:
        reply = await chat(messages, model=OLLAMA_MODEL)
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"No puedo conectar a Ollama en {OLLAMA_HOST}. ¿Está encendido? {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama devolvió {e.response.status_code}. ¿Modelo '{OLLAMA_MODEL}' instalado?")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo no esperado: {e}")
    latency_ms = int((time.monotonic() - t0) * 1000)

    # 5. Clasificar emoción
    input_emotion  = classify(body.text)
    output_emotion = classify(reply)

    # 6. Actualizar historial local (ventana deslizante)
    sess["history"].append({"role": "user",      "content": body.text})
    sess["history"].append({"role": "assistant", "content": reply})
    sess["turn"] += 1
    # Mantener solo los últimos _MAX_HISTORY_TURNS turnos (cada turno = 2 mensajes)
    max_msgs = _MAX_HISTORY_TURNS * 2
    if len(sess["history"]) > max_msgs:
        sess["history"] = sess["history"][-max_msgs:]

    # 7. Almacenar en memory-service (fire-and-forget, no bloquea la respuesta)
    asyncio.create_task(_store_interaction(
        session_id    = sess["session_id"],
        user_id       = user_id,
        input_text    = body.text,
        output_text   = reply,
        input_emotion = input_emotion,
        output_emotion= output_emotion,
        turn          = sess["turn"],
        latency_ms    = latency_ms,
    ))

    # 8. Publicar al gateway (TTS, Face, etc.)
    try:
        await asyncio.gather(
            publish("utterance", {"text": reply}),
            publish("emotion",   {"label": output_emotion})
        )
    except Exception:
        pass

    return ChatOut(reply=reply, emotion=output_emotion, model=OLLAMA_MODEL)


@app.post("/session/reset")
async def session_reset(body: SessionResetIn):
    """Limpia el historial de un usuario y cierra su sesión en memory-service."""
    user_id = body.user or "local"
    sess = _active_sessions.pop(user_id, None)

    if sess:
        # Cerrar sesión en memory-service (best-effort)
        await _memory_post(f"/sessions/{sess['session_id']}/end", {})
        return {"ok": True, "closed_session": sess["session_id"], "turns": sess["turn"]}

    return {"ok": True, "message": "No había sesión activa para ese usuario"}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8801)

if __name__ == "__main__":
    main()
