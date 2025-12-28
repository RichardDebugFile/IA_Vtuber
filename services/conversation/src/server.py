import os, asyncio
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from dotenv import load_dotenv
load_dotenv()  # lee .env (del cwd o padres)

from src.llm_ollama import chat, list_models
from src.emotion import classify
from src.ollama_manager import OllamaManager

GATEWAY_HTTP = os.getenv("GATEWAY_HTTP", "http://127.0.0.1:8765")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")  # pon aquí tu modelo exacto (ej. gemma2:latest / gemma3:instruct)

# Global Ollama manager
ollama_manager: OllamaManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global ollama_manager

    # Startup: Verificar y auto-iniciar Ollama si es necesario
    print(f"[CONVERSATION] Checking Ollama at {OLLAMA_HOST}...")
    ollama_manager = OllamaManager(host=OLLAMA_HOST, model=OLLAMA_MODEL)

    ready, message = await ollama_manager.ensure_ready(auto_start=True)
    if ready:
        print(f"[CONVERSATION] [OK] {message}")
    else:
        print(f"[CONVERSATION] [ERROR] {message}")
        print(f"[CONVERSATION] WARNING: Service will start but may fail on /chat requests")

    yield

    # Shutdown
    ollama_manager = None
    print("[CONVERSATION] Shutdown complete")


app = FastAPI(title="vtuber-conversation", version="0.1.1", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatIn(BaseModel):
    user: str = "local"
    text: str

class ChatOut(BaseModel):
    reply: str
    emotion: str
    model: str

async def publish(topic: str, data: Dict[str, Any]) -> None:
    """Publica un evento al gateway (utterance/emotion)."""
    url = f"{GATEWAY_HTTP}/publish"
    payload = {"topic": topic, "data": data}
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json=payload)  # errores se manejan arriba

@app.get("/health")
async def health():
    """Health check endpoint with Ollama status."""
    ollama_ready = False
    if ollama_manager:
        ollama_ready = await ollama_manager.is_server_running()

    return {
        "ok": True,
        "ollama_host": OLLAMA_HOST,
        "model": OLLAMA_MODEL,
        "ollama_ready": ollama_ready
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
    # System prompt breve (ajústalo a tu estilo)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "Eres una VTuber amable, breve y carismática. Responde en español."},
        {"role": "user", "content": body.text}
    ]
    try:
        reply = await chat(messages, model=OLLAMA_MODEL)
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"No puedo conectar a Ollama en {OLLAMA_HOST}. ¿Está encendido? {e}")
    except httpx.HTTPStatusError as e:
        # Suele pasar si el modelo no existe
        raise HTTPException(status_code=502, detail=f"Ollama devolvió {e.response.status_code}. ¿Modelo '{OLLAMA_MODEL}' instalado?")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo no esperado: {e}")

    emo = classify(reply)

    # Publicar a la app (si el gateway no está, seguimos devolviendo la respuesta)
    try:
        await asyncio.gather(
            publish("utterance", {"text": reply}),
            publish("emotion", {"label": emo})
        )
    except Exception:
        pass

    return ChatOut(reply=reply, emotion=emo, model=OLLAMA_MODEL)

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8801)

if __name__ == "__main__":
    main()
