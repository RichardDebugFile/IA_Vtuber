# services/tts/src/server.py
from __future__ import annotations

import base64
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .engine import TTSEngine

try:
    from .engine_http import HTTPFishEngine, HTTPFishEngineError, HTTPFishBadResponse, HTTPFishServerUnavailable
except Exception:
    HTTPFishEngine = None  # type: ignore
    class HTTPFishEngineError(Exception): ...
    class HTTPFishBadResponse(Exception): ...
    class HTTPFishServerUnavailable(Exception): ...

app = FastAPI(title="vtuber-tts", version="0.2.0")

# Backends disponibles
engine_local = TTSEngine()
engine_http: Optional[HTTPFishEngine] = None
if HTTPFishEngine is not None:
    # Si no pasas base_url, engine_http leerá FISH_TTS_HTTP del .env
    try:
        engine_http = HTTPFishEngine(os.getenv("FISH_TTS_HTTP"))
    except Exception:
        engine_http = None

class SynthesizeIn(BaseModel):
    text: str
    emotion: str = "neutral"
    backend: str = "auto"   # "auto" | "http" | "local"

class SynthesizeOut(BaseModel):
    audio_b64: str
    mime: str = "audio/wav"  # si no es WAV, devolveremos otro mime

def _is_wav(b: bytes) -> bool:
    return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE"

@app.get("/health")
async def health() -> dict:
    http_alive = None
    if engine_http is not None:
        try:
            http_alive = engine_http.health()
        except Exception:
            http_alive = False
    return {"ok": True, "http_backend_alive": http_alive}

@app.post("/synthesize", response_model=SynthesizeOut)
async def synthesize(body: SynthesizeIn) -> SynthesizeOut:
    txt, emo = body.text, body.emotion
    audio: bytes

    # 1) Intentar Fish HTTP si procede
    if body.backend in ("auto", "http") and engine_http is not None:
        try:
            if body.backend == "http" or engine_http.health():
                audio = engine_http.synthesize(txt, emo)
            else:
                raise HTTPFishServerUnavailable("Fish HTTP no responde")
        except (HTTPFishEngineError, HTTPFishBadResponse, HTTPFishServerUnavailable) as e:
            if body.backend == "http":
                raise HTTPException(status_code=502, detail=f"TTS HTTP no disponible: {e}")
            # auto → caemos a local
            audio = engine_local.synthesize(txt, emo)
    else:
        # 2) Forzar local
        audio = engine_local.synthesize(txt, emo)

    mime = "audio/wav" if _is_wav(audio) else "application/octet-stream"
    if mime != "audio/wav":
        # Señal explícita: el stub local no generó WAV real
        # (Tu GUI/assistant puede decidir cómo manejarlo)
        pass

    audio_b64 = base64.b64encode(audio).decode("ascii")
    return SynthesizeOut(audio_b64=audio_b64, mime=mime)

if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8802)
