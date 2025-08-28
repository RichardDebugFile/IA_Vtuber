import os
from typing import List, Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx

from dotenv import load_dotenv
load_dotenv()  # lee .env (del cwd o padres)

from llm_ollama import chat, list_models
from emotion import classify
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")  # pon aquí tu modelo exacto (ej. gemma2:latest / gemma3:instruct)

app = FastAPI(title="vtuber-conversation", version="0.1.1")

class ChatIn(BaseModel):
    user: str = "local"
    text: str

class ChatOut(BaseModel):
    reply: str
    emotion: str
    model: str

@app.get("/health")
async def health():
    return {"ok": True, "ollama_host": OLLAMA_HOST, "model": OLLAMA_MODEL}

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

    return ChatOut(reply=reply, emotion=emo, model=OLLAMA_MODEL)

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8801)
