# services/assistant/src/server.py
from __future__ import annotations

import os
import json
import base64
import asyncio
import uuid
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, Body, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="vtuber-assistant", version="0.1.2")

# ---- Config (por .env) -------------------------------------------------------
GATEWAY_HTTP = os.getenv("GATEWAY_HTTP", "http://127.0.0.1:8765")
CONVERSATION_HTTP = os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")
# Nota: FISH_TTS_HTTP no se usa aquí directamente; el assistant llama al microservicio TTS:
FISH_TTS_HTTP = os.getenv("FISH_TTS_HTTP", "http://127.0.0.1:8080/v1/tts")  # solo informativo
TTS_HTTP = os.getenv("TTS_HTTP", "http://127.0.0.1:8802")  # microservicio TTS (server.py)

# Carpeta para exponer WAV por URL (cuando usas out="url")
AUDIO_OUT_DIR = Path(os.getenv("ASSISTANT_AUDIO_DIR", Path(__file__).resolve().parents[1] / "_out" / "audio"))
AUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(AUDIO_OUT_DIR)), name="media")

# ---- Utilidades --------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def _publish(topic: str, data: dict) -> None:
    """Publica eventos al gateway (no rompe el flujo si falla)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(f"{GATEWAY_HTTP}/publish", json={"topic": topic, "data": data})
    except Exception:
        pass

async def _ask_conversation(text: str) -> tuple[str, str]:
    """Pide respuesta y emoción al microservicio conversation."""
    payload = {"user": "local", "text": text}
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{CONVERSATION_HTTP}/chat", json=payload)
        r.raise_for_status()
        js = r.json()
        return js.get("reply", ""), js.get("emotion", "neutral")

# --- Limpieza de emojis SOLO para TTS -----------------------------------------
_EMOJI_CLASS = re.compile(
    "["                                 # rangos comunes de emoji/pictogramas
    "\U0001F1E6-\U0001F1FF"             # banderas
    "\U0001F300-\U0001F5FF"             # símbolos y pictogramas
    "\U0001F600-\U0001F64F"             # emoticonos
    "\U0001F680-\U0001F6FF"             # transporte/mapas
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"                     # símbolos varios
    "\u2700-\u27BF"                     # dingbats
    "]",
    flags=re.UNICODE,
)
_SKIN_TONE = re.compile("[\U0001F3FB-\U0001F3FF]", re.UNICODE)  # modificadores de tono de piel
_ZWJ_VS = re.compile("[\u200D\uFE0F]", re.UNICODE)              # zero-width joiner y variation selectors
_MULTI_WS = re.compile(r"\s{2,}")

def strip_emoji(s: str) -> str:
    """Elimina pictogramas/emoji y normaliza espacios."""
    if not s:
        return ""
    s = _EMOJI_CLASS.sub("", s)
    s = _SKIN_TONE.sub("", s)
    s = _ZWJ_VS.sub("", s)
    s = _MULTI_WS.sub(" ", s)
    return s.strip()

# --- TTS: llamamos al microservicio /synthesize (voz personalizada) -----------
async def _tts_bytes(text: str, emotion: str) -> bytes:
    """
    Llama al microservicio TTS /synthesize para obtener WAV.
    Ese servicio usa HTTPFishEngine internamente con tu referencia de voz
    (FISH_REF_WAV / FISH_REF_TXT / FISH_REF_ID / FISH_USE_MEMORY_CACHE).
    """
    async with httpx.AsyncClient(timeout=600.0) as c:
        r = await c.post(f"{TTS_HTTP}/synthesize",
                         json={"text": text, "emotion": emotion, "backend": "auto"})
        r.raise_for_status()
        js = r.json()
        mime = js.get("mime", "application/octet-stream")
        if mime != "audio/wav":
            raise HTTPException(status_code=502, detail=f"TTS devolvió mime={mime}, se esperaba audio/wav")
        b64 = js.get("audio_b64", "")
        if not b64:
            raise HTTPException(status_code=502, detail="TTS devolvió audio vacío")
        return base64.b64decode(b64)

# ---- Endpoints ---------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "gateway": GATEWAY_HTTP,
        "conversation": CONVERSATION_HTTP,
        "tts": TTS_HTTP,
        "fish_http": FISH_TTS_HTTP,  # informativo
    }

# 1) Respuesta única JSON (b64 o URL)
@app.post("/api/assistant/aggregate")
async def aggregate(body: dict = Body(...)):
    """
    Body:
      { "text": "hola", "out": "b64|url" }
    - por defecto "b64": devuelve audio_b64
    - "url": guarda WAV y devuelve audio_url
    """
    prompt = (body.get("text") or body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "Falta 'text'")
    out_mode = (body.get("out") or "b64").lower()

    trace_id = str(uuid.uuid4())
    text, emotion = await _ask_conversation(prompt)

    # Publica eventos con el texto ORIGINAL (por si quieres mostrar emojis en GUI)
    await asyncio.gather(
        _publish("utterance", {"text": text, "trace_id": trace_id}),
        _publish("emotion", {"label": emotion, "trace_id": trace_id}),
    )

    # Para TTS: limpiar emojis (evita pronunciarlos)
    tts_text = strip_emoji(text)
    audio = await _tts_bytes(tts_text, emotion)

    if out_mode == "url":
        fname = f"{trace_id}.wav"
        (AUDIO_OUT_DIR / fname).write_bytes(audio)
        audio_url = f"/media/{fname}"
        await _publish("audio", {"audio_url": audio_url, "mime": "audio/wav", "trace_id": trace_id})
        return JSONResponse({
            "text": text, "emotion": emotion,
            "audio_url": audio_url, "audio_mime": "audio/wav",
            "trace_id": trace_id
        })

    # default: base64
    audio_b64 = base64.b64encode(audio).decode("ascii")
    await _publish("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})
    return JSONResponse({
        "text": text, "emotion": emotion,
        "audio_b64": audio_b64, "audio_mime": "audio/wav",
        "trace_id": trace_id
    })

# 2) WAV binario directo (útil para descargar/reproducir)
@app.post("/api/assistant/wav")
async def wav(body: dict = Body(...)):
    """
    Devuelve audio/wav. Metadata en headers (X-Text, X-Emotion, X-Trace-Id).
    Body: { "text": "hola" }
    """
    prompt = (body.get("text") or body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "Falta 'text'")

    trace_id = str(uuid.uuid4())
    text, emotion = await _ask_conversation(prompt)

    await asyncio.gather(
        _publish("utterance", {"text": text, "trace_id": trace_id}),
        _publish("emotion", {"label": emotion, "trace_id": trace_id}),
    )

    tts_text = strip_emoji(text)
    audio = await _tts_bytes(tts_text, emotion)

    # (Opcional) publicar también URL para consumidores WS
    try:
        fname = f"{trace_id}.wav"
        (AUDIO_OUT_DIR / fname).write_bytes(audio)
        await _publish("audio", {"audio_url": f"/media/{fname}", "mime": "audio/wav", "trace_id": trace_id})
    except Exception:
        pass

    headers = {
        "Content-Disposition": f'inline; filename="{trace_id}.wav"',
        "X-Text": text,
        "X-Emotion": emotion,
        "X-Trace-Id": trace_id,
    }
    return Response(content=audio, media_type="audio/wav", headers=headers)

# 3) Streaming SSE: primero texto, luego audio (b64)
@app.post("/api/assistant/stream")
async def stream(body: dict = Body(...)):
    prompt = (body.get("text") or body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "Falta 'text'")

    trace_id = str(uuid.uuid4())

    async def gen():
        text, emotion = await _ask_conversation(prompt)

        await asyncio.gather(
            _publish("utterance", {"text": text, "trace_id": trace_id}),
            _publish("emotion", {"label": emotion, "trace_id": trace_id}),
        )
        # Evento de texto (original, con emojis si los hay)
        yield _sse("text", {"text": text, "emotion": emotion, "trace_id": trace_id})

        # Audio con texto limpiado
        tts_text = strip_emoji(text)
        audio = await _tts_bytes(tts_text, emotion)
        audio_b64 = base64.b64encode(audio).decode("ascii")
        await _publish("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})

        yield _sse("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})

    return StreamingResponse(gen(), media_type="text/event-stream")
