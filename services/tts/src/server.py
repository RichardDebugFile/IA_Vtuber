from __future__ import annotations

import base64
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .engine import TTSEngine
from .conversation_client import ConversationClient

app = FastAPI(title="vtuber-tts", version="0.1.0")
engine = TTSEngine()
conv_client = ConversationClient()

class SpeakIn(BaseModel):
    text: str
    user: str = "local"

class SpeakOut(BaseModel):
    reply: str
    emotion: str
    audio_b64: str

@app.get("/health")
async def health() -> dict:
    return {"ok": True}

@app.post("/speak", response_model=SpeakOut)
async def speak(body: SpeakIn) -> SpeakOut:
    try:
        reply, emotion = await conv_client.ask(body.text, body.user)
    except Exception as e:  # pragma: no cover - simple passthrough
        raise HTTPException(status_code=502, detail=f"Conversation service error: {e}")

    audio_bytes = engine.synthesize(reply, emotion)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return SpeakOut(reply=reply, emotion=emotion, audio_b64=audio_b64)

if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8802)
