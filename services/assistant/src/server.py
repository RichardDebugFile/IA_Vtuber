from __future__ import annotations

import os
import json
import base64
import asyncio
import uuid
import re
import io
import wave
from pathlib import Path
from typing import List, Tuple, Dict

import time
import httpx
from fastapi import FastAPI, Body, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="vtuber-assistant", version="1.0.0")


try:
    from dotenv import load_dotenv
    # Busca el .env en la raíz del repo (…/services/assistant/src/server.py -> …/…/…/IA_Vtuber)
    ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
    if ROOT_ENV.exists():
        load_dotenv(ROOT_ENV)
    else:
        # Fallback: busca hacia arriba desde el cwd
        load_dotenv()
except Exception:
    # Si no está python-dotenv, simplemente sigue con los getenv que ya tienes
    pass




# ---- Config (.env) -----------------------------------------------------------
GATEWAY_HTTP = os.getenv("GATEWAY_HTTP", "http://127.0.0.1:8800")
CONVERSATION_HTTP = os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")
FISH_TTS_HTTP = os.getenv("FISH_TTS_HTTP", "http://127.0.0.1:8080/v1/tts")  # informativo
TTS_HTTP = os.getenv("TTS_HTTP", "http://127.0.0.1:8802")
CHUNK_OUT_MODE = os.getenv("ASSISTANT_CHUNK_OUT", "url").lower()  # b64 | url

# Carpeta para exponer WAV por URL
AUDIO_OUT_DIR = Path(os.getenv("ASSISTANT_AUDIO_DIR", Path(__file__).resolve().parents[1] / "_out" / "audio"))
AUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(AUDIO_OUT_DIR)), name="media")

# === Tuning ==============================================================
SEC_PER_WORD         = float(os.getenv("TTS_SEC_PER_WORD", "1.2"))   # solo informativo en timeline

# Pausas (ms) por puntuación entre chunks
PAUSE_COMMA_MS       = int(os.getenv("ASSISTANT_PAUSE_COMMA_MS", "120"))
PAUSE_STOP_MS        = int(os.getenv("ASSISTANT_PAUSE_STOP_MS", "220"))  # . ! ? …
PAUSE_DEFAULT_MS     = int(os.getenv("ASSISTANT_PAUSE_DEFAULT_MS", "80"))

# Gap mínimo de seguridad (ms) si no hay puntuación
GAP_MIN_MS           = int(float(os.getenv("ASSISTANT_GAP_MIN_S", "0.08")) * 1000)

# Concurrencia de TTS (2 si tu 3080 aguanta; si no, 1)
TTS_CONCURRENCY      = max(1, int(os.getenv("ASSISTANT_TTS_CONCURRENCY", "2")))
PREBUFFER_CHUNKS     = max(1, int(os.getenv("ASSISTANT_PREBUFFER_CHUNKS", "1")))  # cuántos sintetizar antes de emitir el 1º

# Segmentación natural
LONG_SPLIT_WORDS     = int(os.getenv("ASSISTANT_LONG_SPLIT_WORDS", "28"))
LONG_MIN_HALF        = int(os.getenv("ASSISTANT_LONG_MIN_HALF", "10"))
SHORT_MERGE_HEAD     = int(os.getenv("ASSISTANT_SHORT_MERGE_HEAD", "4"))

# Primer chunk muy corto para arrancar rápido
FIRST_MAX_WORDS      = int(os.getenv("ASSISTANT_FIRST_MAX_WORDS", "6"))
FIRST_MIN_WORDS      = int(os.getenv("ASSISTANT_FIRST_MIN_WORDS", "2"))

_word_re = re.compile(r"\w+", re.UNICODE)

# ---- Utilidades --------------------------------------------------------------
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def _publish(topic: str, data: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(f"{GATEWAY_HTTP}/publish", json={"topic": topic, "data": data})
    except Exception:
        pass

async def _ask_conversation(text: str) -> tuple[str, str]:
    payload = {"user": "local", "text": text}
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(f"{CONVERSATION_HTTP}/chat", json=payload)
        r.raise_for_status()
        js = r.json()
        return js.get("reply", ""), js.get("emotion", "neutral")

def _now() -> float:
    return time.perf_counter()

# ---- Limpieza de emojis SOLO para TTS ----------------------------------------
_EMOJI_CLASS = re.compile(
    "["  # rangos comunes de emoji/pictogramas
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]", re.UNICODE
)
_SKIN_TONE = re.compile("[\U0001F3FB-\U0001F3FF]", re.UNICODE)
_ZWJ_VS = re.compile("[\u200D\uFE0F]", re.UNICODE)
_MULTI_WS = re.compile(r"\s{2,}")

def strip_emoji(s: str) -> str:
    if not s:
        return ""
    s = _EMOJI_CLASS.sub("", s)
    s = _SKIN_TONE.sub("", s)
    s = _ZWJ_VS.sub("", s)
    s = _MULTI_WS.sub(" ", s)
    return s.strip()

# ---- TTS (voz personalizada) -------------------------------------------------
async def _tts_bytes(text: str, emotion: str) -> bytes:
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

def _wav_duration_s(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            return wf.getnframes() / max(1, wf.getframerate())
    except Exception:
        return 0.0

# ---- Segmentación natural y “primer chunk corto” -----------------------------
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?…])\s+", re.UNICODE)
_TAIL_BAD = {
    "y","o","u","e","ni","que","de","con","a","en","por","para","pero","aunque","porque","así","asi"
}

def _split_sentences_es(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return parts if parts else [text.strip()]

def _balance_two_halves(sentence: str) -> list[str]:
    words = sentence.split()
    n = len(words)
    if n <= LONG_SPLIT_WORDS:
        return [sentence]
    mid = n // 2

    # intenta en comas cercanas al centro
    comma_idx = None; best = 10**9
    for i, w in enumerate(words):
        if w.endswith(",") and LONG_MIN_HALF <= i <= n - LONG_MIN_HALF:
            d = abs(i - mid)
            if d < best:
                best, comma_idx = d, i
    if comma_idx is None:
        cut = max(LONG_MIN_HALF, min(n - LONG_MIN_HALF, mid))
    else:
        cut = comma_idx + 1

    left  = words[:cut]
    right = words[cut:]

    # evita conectores huérfanos
    def bad_end(ws: List[str]) -> bool:
        return ws and ws[-1].lower().strip("¡!¿?.,;:") in _TAIL_BAD
    def bad_start(ws: List[str]) -> bool:
        return ws and ws[0].lower().strip("¡!¿?.,;:") in _TAIL_BAD

    # mueve 1-2 tokens para evitar “así que” dividido raro
    shift_guard = 0
    while (bad_end(left) or bad_start(right)) and 0 < len(left) < len(words) and shift_guard < 3:
        if bad_end(left) and len(right) >= 1:
            right.insert(0, left.pop())        # mueve al inicio de right
        elif bad_start(right) and len(left) >= 1:
            left.append(right.pop(0))          # mueve al final de left
        shift_guard += 1

    return [
        " ".join(left).strip(", "),
        " ".join(right).strip(", "),
    ]

def _merge_short_head(segments: list[str]) -> list[str]:
    if not segments:
        return segments
    out = []
    i = 0
    while i < len(segments):
        s = segments[i]
        if i == 0 and len(s.split()) <= SHORT_MERGE_HEAD and i + 1 < len(segments):
            out.append((s + " " + segments[i + 1]).strip())
            i += 2
        else:
            out.append(s)
            i += 1
    return out

def _avoid_orphan_tails(segments: list[str]) -> list[str]:
    if not segments:
        return segments
    out=[]; i=0
    while i < len(segments):
        cur = segments[i]; toks = cur.split()
        if toks and toks[-1].lower().strip("¡!¿?.,;:") in _TAIL_BAD and (i+1) < len(segments):
            out.append((cur.rstrip(", ") + " " + segments[i+1]).strip()); i += 2
        else:
            out.append(cur); i += 1
    return out

def _force_first_short(segs: list[str]) -> list[str]:
    """Asegura que el primer chunk sea muy corto (<= FIRST_MAX_WORDS)."""
    if not segs:
        return segs
    first = segs[0]
    w = first.split()
    if len(w) <= FIRST_MAX_WORDS:
        return segs

    # corta por primera puntuación fuerte dentro de las primeras 10 palabras
    cut_idx = -1
    max_scan = min(len(w), max(FIRST_MAX_WORDS + 4, 10))
    for i in range(min(max_scan, len(w))):
        if any(w[i].endswith(p) for p in [",", ".", "!", "?", "…", ";", ":"]):
            cut_idx = i + 1
            break
    if cut_idx == -1:
        cut_idx = FIRST_MAX_WORDS

    head = " ".join(w[:cut_idx]).strip()
    tail = " ".join(w[cut_idx:] + ([] if len(segs) == 1 else [])).strip()
    new_segs = [head]
    if tail:
        new_segs.append(tail)
        new_segs.extend(segs[1:])
    else:
        new_segs.extend(segs[1:])
    return new_segs

def segment_text_for_tts(full_text: str) -> list[str]:
    clean = strip_emoji(full_text)
    base: list[str] = []
    for sent in _split_sentences_es(clean):
        if not sent:
            continue
        w = sent.split()
        if len(w) > LONG_SPLIT_WORDS:
            base.extend(_balance_two_halves(sent))
        else:
            base.append(sent)

    base = _merge_short_head(base)
    base = _avoid_orphan_tails(base)
    base = _force_first_short(base)

    # Normaliza
    return [re.sub(r"\s+", " ", s).strip() for s in base if s.strip()]

# ---- Pausas por puntuación ---------------------------------------------------
def _pause_for_chunk(text: str) -> int:
    t = text.rstrip()
    if not t:
        return GAP_MIN_MS
    last = t[-1]
    if last in [".", "!", "?", "…"]:
        return PAUSE_STOP_MS
    if last in [",", ";", ":"]:
        return PAUSE_COMMA_MS
    return PAUSE_DEFAULT_MS

# ---- Endpoints básicos -------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "gateway": GATEWAY_HTTP,
        "conversation": CONVERSATION_HTTP,
        "tts": TTS_HTTP,
        "fish_http": FISH_TTS_HTTP,
        "tuning": {
            "SEC_PER_WORD": SEC_PER_WORD,
            "TTS_CONCURRENCY": TTS_CONCURRENCY,
            "PREBUFFER_CHUNKS": PREBUFFER_CHUNKS,
            "GAP_MIN_MS": GAP_MIN_MS,
            "PAUSE_COMMA_MS": PAUSE_COMMA_MS,
            "PAUSE_STOP_MS": PAUSE_STOP_MS,
            "PAUSE_DEFAULT_MS": PAUSE_DEFAULT_MS,
            "FIRST_MAX_WORDS": FIRST_MAX_WORDS,
        },
    }

# 1) Respuesta única JSON
@app.post("/api/assistant/aggregate")
async def aggregate(body: dict = Body(...)):
    prompt = (body.get("text") or body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "Falta 'text'")
    out_mode = (body.get("out") or "b64").lower()

    trace_id = str(uuid.uuid4())
    text, emotion = await _ask_conversation(prompt)
    await asyncio.gather(
        _publish("utterance", {"text": text, "trace_id": trace_id}),
        _publish("emotion", {"label": emotion, "trace_id": trace_id}),
    )
    tts_text = strip_emoji(text)
    audio = await _tts_bytes(tts_text, emotion)

    if out_mode == "url":
        fname = f"{trace_id}.wav"; (AUDIO_OUT_DIR / fname).write_bytes(audio)
        audio_url = f"/media/{fname}"
        await _publish("audio", {"audio_url": audio_url, "mime": "audio/wav", "trace_id": trace_id})
        return JSONResponse({"text": text, "emotion": emotion, "audio_url": audio_url, "audio_mime": "audio/wav", "trace_id": trace_id})

    audio_b64 = base64.b64encode(audio).decode("ascii")
    await _publish("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})
    return JSONResponse({"text": text, "emotion": emotion, "audio_b64": audio_b64, "audio_mime": "audio/wav", "trace_id": trace_id})

# 2) WAV binario directo
@app.post("/api/assistant/wav")
async def wav(body: dict = Body(...)):
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

    try:
        fname = f"{trace_id}.wav"; (AUDIO_OUT_DIR / fname).write_bytes(audio)
        await _publish("audio", {"audio_url": f"/media/{fname}", "mime": "audio/wav", "trace_id": trace_id})
    except Exception:
        pass

    headers = {
        "Content-Disposition": f'inline; filename="{trace_id}.wav"',
        "X-Text": text, "X-Emotion": emotion, "X-Trace-Id": trace_id,
    }
    return Response(content=audio, media_type="audio/wav", headers=headers)

# 3) Streaming SSE (texto completo primero, luego audio completo)
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
        yield _sse("text", {"text": text, "emotion": emotion, "trace_id": trace_id})

        tts_text = strip_emoji(text)
        audio = await _tts_bytes(tts_text, emotion)
        audio_b64 = base64.b64encode(audio).decode("ascii")
        await _publish("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})
        yield _sse("audio", {"audio_b64": audio_b64, "mime": "audio/wav", "trace_id": trace_id})

    return StreamingResponse(gen(), media_type="text/event-stream")

# 4) Streaming por CHUNKS: arranque rápido + concurrencia + pausas por puntuación
@app.post("/api/assistant/stream-chunks")
async def stream_chunks(body: dict = Body(...)):
    """
    - Primer chunk forzado corto -> primer audio sale pronto.
    - Concurrencia (ventana deslizante) para sintetizar por detrás.
    - Pacing reactivo: offset_i = prev_end + pause(puntuación), limitado por ready_time.
    - Sin warm-up artificial; start_delay=0.
    """
    prompt = (body.get("text") or body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "Falta 'text'")
    out_mode = (body.get("out") or CHUNK_OUT_MODE).lower()
    if out_mode not in ("b64", "url"):
        out_mode = "url"

    trace_id = str(uuid.uuid4())

    async def synth(seg_text: str, emotion: str) -> Tuple[bytes, float, float, int]:
        t0 = _now()
        audio = await _tts_bytes(strip_emoji(seg_text), emotion)
        dur_s = _wav_duration_s(audio)
        tts_ms = int((_now() - t0) * 1000)
        return audio, dur_s, _now(), tts_ms

    async def gen():
        # 1) LLM
        full_text, emotion = await _ask_conversation(prompt)
        await asyncio.gather(
            _publish("utterance", {"text": full_text, "trace_id": trace_id}),
            _publish("emotion", {"label": emotion, "trace_id": trace_id}),
        )

        # 2) Segmentación
        segments = segment_text_for_tts(full_text)
        total = len(segments)
        if total == 0:
            yield _sse("timeline", {"start_delay_ms": 0, "gap_min_ms": GAP_MIN_MS, "sec_per_word": SEC_PER_WORD, "trace_id": trace_id})
            yield _sse("done", {"total": 0, "trace_id": trace_id})
            return

        # 3) Lanzar tareas TTS con ventana de concurrencia
        sem = asyncio.Semaphore(TTS_CONCURRENCY)
        in_flight: Dict[int, asyncio.Task] = {}

        async def start_task(idx: int):
            async with sem:
                return await synth(segments[idx], emotion)

        next_idx = 0
        while next_idx < total and len(in_flight) < TTS_CONCURRENCY:
            in_flight[next_idx] = asyncio.create_task(start_task(next_idx))
            next_idx += 1

        # 4) Espera el primer audio para arrancar (pero es corto, sale pronto)
        audio0, dur0_s, ready0, tts0 = await in_flight.pop(0)
        dur0_ms = int(dur0_s * 1000)

        # Encolamos las siguientes tareas para mantener la ventana llena
        while next_idx < total and len(in_flight) < TTS_CONCURRENCY:
            in_flight[next_idx] = asyncio.create_task(start_task(next_idx))
            next_idx += 1

        # 5) Timeline: sin warm-up; el cliente puede empezar en cuanto reciba el audio 0
        yield _sse("timeline", {"start_delay_ms": 0, "gap_min_ms": GAP_MIN_MS, "sec_per_word": SEC_PER_WORD, "trace_id": trace_id})

        # 6) Base temporal
        t_anchor = _now()  # referencia para offsets (cuando emitimos el 1er audio)
        prev_offset_ms = 0
        prev_end_ms = dur0_ms
        prev_text = segments[0]
        pause_ms_prev = _pause_for_chunk(prev_text)

        # SEGMENT 0
        yield _sse("segment", {
            "index": 0,
            "text": segments[0],
            "total": total,
            "emotion": emotion,
            "trace_id": trace_id,
            "offset_ms": 0,
            "tts_ms": tts0,
            "duration_ms": dur0_ms,
            "pause_ms": pause_ms_prev,
        })

        # AUDIO 0
        if out_mode == "url":
            fname = f"{trace_id}_000.wav"
            (AUDIO_OUT_DIR / fname).write_bytes(audio0)
            url = f"/media/{fname}"
            await _publish("audio", {"audio_url": url, "mime": "audio/wav", "trace_id": trace_id, "kind": "chunk", "index": 0, "tts_ms": tts0})
            yield _sse("audio", {"index": 0, "audio_url": url, "mime": "audio/wav", "duration": dur0_s, "duration_ms": dur0_ms, "trace_id": trace_id, "offset_ms": 0, "tts_ms": tts0})
        else:
            b64 = base64.b64encode(audio0).decode("ascii")
            await _publish("audio", {"audio_b64": b64, "mime": "audio/wav", "trace_id": trace_id, "kind": "chunk", "index": 0, "tts_ms": tts0})
            yield _sse("audio", {"index": 0, "audio_b64": b64, "mime": "audio/wav", "duration": dur0_s, "duration_ms": dur0_ms, "trace_id": trace_id, "offset_ms": 0, "tts_ms": tts0})

        # 7) Resto en orden, usando pausas por puntuación + concurrencia real
        i = 1
        while i < total:
            # asegura tarea
            if i not in in_flight:
                in_flight[i] = asyncio.create_task(start_task(i))
                if next_idx < total:
                    in_flight[next_idx] = asyncio.create_task(start_task(next_idx))
                    next_idx += 1

            audio_i, dur_i_s, ready_i, tts_i = await in_flight.pop(i)
            dur_i_ms = int(dur_i_s * 1000)

            pause_ms = _pause_for_chunk(prev_text)
            desired_offset_ms = prev_offset_ms + prev_end_ms + max(GAP_MIN_MS, pause_ms)

            ready_rel_ms = int(max(0.0, (_now() - t_anchor) * 1000.0))  # instante actual (nosotros ya tenemos audio_i en mano)
            # lo importante: no planificamos en el pasado; si ya tenemos el audio antes del desired, mantenemos desired
            offset_ms = max(desired_offset_ms, ready_rel_ms)

            # SEGMENT i
            yield _sse("segment", {
                "index": i,
                "text": segments[i],
                "total": total,
                "emotion": emotion,
                "trace_id": trace_id,
                "offset_ms": offset_ms,
                "tts_ms": tts_i,
                "duration_ms": dur_i_ms,
                "pause_ms": pause_ms,
            })

            # AUDIO i
            if out_mode == "url":
                fname = f"{trace_id}_{i:03d}.wav"
                (AUDIO_OUT_DIR / fname).write_bytes(audio_i)
                url = f"/media/{fname}"
                await _publish("audio", {"audio_url": url, "mime": "audio/wav", "trace_id": trace_id, "kind": "chunk", "index": i, "tts_ms": tts_i})
                yield _sse("audio", {"index": i, "audio_url": url, "mime": "audio/wav", "duration": dur_i_s, "duration_ms": dur_i_ms, "trace_id": trace_id, "offset_ms": offset_ms, "tts_ms": tts_i})
            else:
                b64 = base64.b64encode(audio_i).decode("ascii")
                await _publish("audio", {"audio_b64": b64, "mime": "audio/wav", "trace_id": trace_id, "kind": "chunk", "index": i, "tts_ms": tts_i})
                yield _sse("audio", {"index": i, "audio_b64": b64, "mime": "audio/wav", "duration": dur_i_s, "duration_ms": dur_i_ms, "trace_id": trace_id, "offset_ms": offset_ms, "tts_ms": tts_i})

            prev_offset_ms = offset_ms
            prev_end_ms = dur_i_ms
            prev_text = segments[i]
            i += 1

        yield _sse("done", {"total": total, "trace_id": trace_id})

    return StreamingResponse(gen(), media_type="text/event-stream")
