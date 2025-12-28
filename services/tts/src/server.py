# services/tts/src/server.py
from __future__ import annotations

import base64
import io
import os
import time
import uuid
import wave
import yaml
from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Import stub engine only for backward compatibility
from .engine import TTSEngine
from .logging_config import logger, log_synthesis
from . import metrics

try:
    from .engine_http import HTTPFishEngine, HTTPFishEngineError, HTTPFishBadResponse, HTTPFishServerUnavailable
except Exception:
    HTTPFishEngine = None  # type: ignore
    class HTTPFishEngineError(Exception): ...
    class HTTPFishBadResponse(Exception): ...
    class HTTPFishServerUnavailable(Exception): ...

try:
    from .conversation_tts import ConversationTTS
except Exception as e:
    logger.warning(f"ConversationTTS not available: {e}")
    ConversationTTS = None  # type: ignore

# Initialize FastAPI app
app = FastAPI(title="vtuber-tts", version="0.4.0")

# Add Prometheus metrics endpoint
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import REGISTRY, generate_latest

# Instrument FastAPI with basic metrics
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY)

# Startup/Shutdown events
@app.on_event("startup")
async def startup_event():
    """Log service startup and initialize metrics."""
    logger.info("TTS Service starting up", version="0.4.0")

    # Instrument FastAPI
    instrumentator.instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

    # Initialize Fish Audio health metric
    if engine_http is not None:
        logger.info("Fish Audio HTTP backend configured", url=engine_http.url)
        is_healthy = engine_http.health()
        metrics.update_fish_health(is_healthy)
        if is_healthy:
            logger.info("Fish Audio backend is healthy")
        else:
            logger.warning("Fish Audio backend health check failed at startup")
    else:
        logger.warning("Fish Audio HTTP backend NOT configured - only stub available")
        metrics.update_fish_health(False)

@app.on_event("shutdown")
async def shutdown_event():
    """Log service shutdown."""
    logger.info("TTS Service shutting down")

# Primary backend: Fish Audio HTTP
engine_http: Optional[HTTPFishEngine] = None
if HTTPFishEngine is not None:
    # Si no pasas base_url, engine_http leerá FISH_TTS_HTTP del .env
    try:
        engine_http = HTTPFishEngine(os.getenv("FISH_TTS_HTTP"))
    except Exception:
        engine_http = None

# Fallback stub engine (DEPRECATED - only for testing)
engine_local = TTSEngine()

# Conversation TTS engine (optimized for low latency)
conversation_engine: Optional[ConversationTTS] = None
if ConversationTTS is not None and engine_http is not None:
    try:
        conversation_engine = ConversationTTS(engine_http, max_parallel=6)
        logger.info("ConversationTTS engine initialized with max_parallel=6")
    except Exception as e:
        logger.error(f"Failed to initialize ConversationTTS: {e}")
        conversation_engine = None

class SynthesizeIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize (max 5000 chars)")
    emotion: str = "neutral"
    backend: str = "http"   # "http" | "local" (local is deprecated stub)
    max_words_per_chunk: Optional[int] = Field(10, ge=3, le=20, description="Max words per chunk for streaming (3-20)")

class SynthesizeOut(BaseModel):
    audio_b64: str
    mime: str = "audio/wav"  # si no es WAV, devolveremos otro mime

def _is_wav(b: bytes) -> bool:
    return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE"

def _add_silence_padding(audio_bytes: bytes, padding_seconds: float = 0.5) -> bytes:
    """
    Add silence padding to the end of a WAV file to prevent cutoff.

    Args:
        audio_bytes: Original WAV file bytes
        padding_seconds: Duration of silence to add (default: 0.5s)

    Returns:
        Modified WAV file bytes with silence padding
    """
    try:
        # Read original WAV file
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav:
            params = wav.getparams()
            frames = wav.readframes(params.nframes)

        # Calculate silence duration in frames
        silence_frames = int(params.framerate * padding_seconds)
        silence_bytes = b'\x00' * (silence_frames * params.sampwidth * params.nchannels)

        # Create new WAV with padding
        output = io.BytesIO()
        with wave.open(output, 'wb') as out_wav:
            out_wav.setparams(params)
            out_wav.writeframes(frames + silence_bytes)

        return output.getvalue()
    except Exception as e:
        logger.warning(f"Failed to add silence padding: {e}, returning original audio")
        return audio_bytes

@app.get("/health")
async def health() -> dict:
    """Health check endpoint (liveness probe)."""
    return {"ok": True, "status": "alive"}

@app.get("/health/ready")
async def readiness() -> dict:
    """Readiness check endpoint - checks if service can handle requests."""
    http_alive = None
    if engine_http is not None:
        try:
            http_alive = engine_http.health()
            metrics.update_fish_health(http_alive)
            if not http_alive:
                logger.warning("Fish Audio HTTP backend health check failed")
                return {"ok": False, "status": "not_ready", "reason": "fish_audio_unhealthy"}
        except Exception as e:
            logger.error(f"Fish Audio health check error: {e}")
            metrics.update_fish_health(False)
            http_alive = False
            return {"ok": False, "status": "not_ready", "reason": f"health_check_error: {e}"}

    return {"ok": True, "status": "ready", "backend_alive": http_alive}

@app.get("/emotions")
async def list_emotions() -> dict:
    """List all available emotions for the AI to use.

    Returns a dictionary with:
    - emotions: List of emotion names
    - count: Total number of emotions
    - categories: Emotions organized by category
    """
    presets_path = Path(__file__).parent / "voices" / "presets.yaml"

    try:
        with open(presets_path, "r", encoding="utf-8") as f:
            emotion_map: Dict[str, str] = yaml.safe_load(f) or {}

        emotions = list(emotion_map.keys())

        # Categorize emotions (based on comments in presets.yaml)
        basic_emotions = [
            "neutral", "happy", "angry", "sad", "surprised", "excited",
            "confused", "upset", "fear", "asco", "love", "bored", "sleeping", "thinking"
        ]

        advanced_emotions = [
            "embarrassed", "proud", "grateful", "sarcastic",
            "amused", "interested", "comforting", "playful"
        ]

        return {
            "ok": True,
            "emotions": emotions,
            "count": len(emotions),
            "categories": {
                "basic": [e for e in basic_emotions if e in emotions],
                "advanced": [e for e in advanced_emotions if e in emotions]
            },
            "fish_markers": {emotion: emotion_map[emotion] for emotion in emotions}
        }
    except Exception as e:
        logger.error(f"Failed to load emotions from presets.yaml: {e}")
        return {
            "ok": False,
            "error": str(e),
            "emotions": [],
            "count": 0
        }

@app.post("/synthesize", response_model=SynthesizeOut)
async def synthesize(body: SynthesizeIn, request: Request) -> SynthesizeOut:
    """Synthesize speech from text using Fish Audio.

    Args:
        body: Request body with text, emotion, and backend selection
        request: FastAPI request object (for logging)

    Returns:
        Audio encoded as base64 with MIME type

    Raises:
        HTTPException 502: If Fish Audio HTTP backend is unavailable
        HTTPException 422: If input validation fails (handled by Pydantic)
    """
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    txt, emo = body.text, body.emotion
    audio: bytes
    success = False
    error_msg = None

    logger.info(
        "Synthesis request",
        request_id=request_id,
        text_length=len(txt),
        emotion=emo,
        backend=body.backend,
        client=request.client.host if request.client else "unknown"
    )

    # Use context manager for automatic metrics
    with metrics.RequestMetrics(body.backend, emo):
        try:
            # Primary: Fish Audio HTTP backend
            if body.backend == "http":
                if engine_http is None:
                    error_msg = "Fish Audio HTTP backend not configured"
                    logger.error(error_msg, request_id=request_id)
                    metrics.record_error(body.backend, "not_configured", emo)
                    raise HTTPException(
                        status_code=502,
                        detail=f"{error_msg}. Check FISH_TTS_HTTP environment variable."
                    )
                try:
                    synth_start = time.time()

                    # Use ConversationTTS if available for parallel processing
                    if conversation_engine is not None:
                        logger.debug("Using ConversationTTS for synthesis", request_id=request_id)
                        audio = await conversation_engine.synthesize_complete(txt, emo)
                    else:
                        logger.debug("Using direct engine_http (ConversationTTS unavailable)", request_id=request_id)
                        audio = engine_http.synthesize(txt, emo)

                    synth_duration = time.time() - synth_start

                    # Record synthesis metrics
                    metrics.record_synthesis(
                        backend=body.backend,
                        emotion=emo,
                        duration_seconds=synth_duration,
                        text_length=len(txt),
                        audio_size=len(audio)
                    )
                except (HTTPFishEngineError, HTTPFishBadResponse, HTTPFishServerUnavailable) as e:
                    error_msg = str(e)
                    logger.error(
                        "Fish Audio synthesis failed",
                        request_id=request_id,
                        error=error_msg,
                        text_length=len(txt),
                        emotion=emo
                    )
                    # Record error metrics
                    error_type = "server_unavailable" if isinstance(e, HTTPFishServerUnavailable) else "bad_response"
                    metrics.record_error(body.backend, error_type, emo)
                    raise HTTPException(
                        status_code=502,
                        detail=f"Fish Audio TTS service unavailable: {e}"
                    )
            elif body.backend == "local":
                # DEPRECATED: Stub for testing only - does not produce real audio
                logger.debug("Using deprecated local stub backend", request_id=request_id)
                synth_start = time.time()
                audio = engine_local.synthesize(txt, emo)
                synth_duration = time.time() - synth_start

                metrics.record_synthesis(
                    backend=body.backend,
                    emotion=emo,
                    duration_seconds=synth_duration,
                    text_length=len(txt),
                    audio_size=len(audio)
                )
            else:
                error_msg = f"Invalid backend: {body.backend}"
                logger.warning(error_msg, request_id=request_id)
                metrics.record_error(body.backend, "invalid_backend", emo)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid backend '{body.backend}'. Use 'http' for production or 'local' for testing stub."
                )

            # Validate WAV format
            mime = "audio/wav" if _is_wav(audio) else "application/octet-stream"
            if mime != "audio/wav" and body.backend == "http":
                # HTTP backend should always return WAV
                error_msg = "Invalid audio format (not WAV)"
                logger.error(error_msg, request_id=request_id, mime=mime)
                metrics.record_error(body.backend, "invalid_format", emo)
                raise HTTPException(
                    status_code=502,
                    detail="Fish Audio returned invalid audio format (not WAV)"
                )

            # Add silence padding to prevent audio cutoff at the end
            if mime == "audio/wav":
                audio = _add_silence_padding(audio, padding_seconds=0.5)

            audio_b64 = base64.b64encode(audio).decode("ascii")
            success = True

            # Log successful synthesis
            duration_ms = (time.time() - start_time) * 1000
            log_synthesis(
                text_length=len(txt),
                emotion=emo,
                backend=body.backend,
                duration_ms=duration_ms,
                success=True,
                request_id=request_id,
                audio_size=len(audio)
            )

            return SynthesizeOut(audio_b64=audio_b64, mime=mime)

        except HTTPException:
            # Re-raise HTTP exceptions
            duration_ms = (time.time() - start_time) * 1000
            log_synthesis(
                text_length=len(txt),
                emotion=emo,
                backend=body.backend,
                duration_ms=duration_ms,
                success=False,
                request_id=request_id,
                error=error_msg
            )
            raise
        except Exception as e:
            # Catch unexpected errors
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Unexpected error: {e}"
            logger.exception("Unexpected error in synthesis", request_id=request_id)
            metrics.record_error(body.backend, "unexpected", emo)
            log_synthesis(
                text_length=len(txt),
                emotion=emo,
                backend=body.backend,
                duration_ms=duration_ms,
                success=False,
                request_id=request_id,
                error=error_msg
            )
            raise HTTPException(status_code=500, detail=error_msg)

@app.post("/synthesize_streaming")
async def synthesize_streaming(body: SynthesizeIn, request: Request):
    """
    Synthesize speech with optimized streaming for low latency.

    Uses intelligent comma-based segmentation to minimize Time To First Audio (TTFA).
    Ideal for streamer mode (10-20 words, <4s response time).

    Args:
        body: Request body with text, emotion, and backend selection
        request: FastAPI request object (for logging)

    Returns:
        Server-Sent Events (SSE) stream with audio chunks

    Raises:
        HTTPException 502: If Fish Audio HTTP backend is unavailable
        HTTPException 422: If input validation fails
        HTTPException 501: If ConversationTTS is not available
    """
    from fastapi.responses import StreamingResponse
    import json

    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    txt, emo = body.text, body.emotion

    logger.info(
        "Streaming synthesis request",
        request_id=request_id,
        text_length=len(txt),
        emotion=emo,
        backend=body.backend,
        client=request.client.host if request.client else "unknown"
    )

    # Verificar que ConversationTTS esté disponible
    if conversation_engine is None:
        error_msg = "ConversationTTS not available (required for streaming)"
        logger.error(error_msg, request_id=request_id)
        raise HTTPException(status_code=501, detail=error_msg)

    # Verificar backend
    if body.backend != "http":
        error_msg = f"Streaming only available with 'http' backend (got '{body.backend}')"
        logger.error(error_msg, request_id=request_id)
        raise HTTPException(status_code=400, detail=error_msg)

    if engine_http is None:
        error_msg = "Fish Audio HTTP backend not configured"
        logger.error(error_msg, request_id=request_id)
        raise HTTPException(
            status_code=502,
            detail=f"{error_msg}. Check FISH_TTS_HTTP environment variable."
        )

    async def generate_chunks():
        """Generator for SSE streaming"""
        chunk_count = 0
        total_audio_size = 0
        first_chunk_time = None

        try:
            # Import locally to get word count utility
            from .conversation_tts import SentenceSplitter

            async for audio_chunk in conversation_engine.synthesize_streaming_optimized(
                txt, emo, max_words_per_chunk=body.max_words_per_chunk
            ):
                if first_chunk_time is None:
                    first_chunk_time = time.time() - start_time
                    logger.info(
                        f"First chunk generated (TTFA)",
                        request_id=request_id,
                        ttfa_ms=first_chunk_time * 1000
                    )

                chunk_count += 1
                total_audio_size += len(audio_chunk.audio_bytes)

                # Encode audio to base64
                audio_b64 = base64.b64encode(audio_chunk.audio_bytes).decode("ascii")

                # Prepare chunk data
                chunk_data = {
                    "chunk_index": chunk_count,
                    "audio_b64": audio_b64,
                    "text": audio_chunk.text,
                    "word_count": SentenceSplitter.count_words(audio_chunk.text),
                    "generation_time_ms": audio_chunk.duration_ms,
                    "emotion": audio_chunk.emotion
                }

                # Send as SSE
                yield f"data: {json.dumps(chunk_data)}\n\n"

                logger.debug(
                    f"Chunk {chunk_count} sent",
                    request_id=request_id,
                    text_preview=audio_chunk.text[:40],
                    size_kb=len(audio_chunk.audio_bytes) / 1024
                )

            # Send completion event
            total_duration = time.time() - start_time
            completion_data = {
                "event": "complete",
                "total_chunks": chunk_count,
                "total_audio_size": total_audio_size,
                "total_duration_ms": total_duration * 1000,
                "ttfa_ms": first_chunk_time * 1000 if first_chunk_time else 0
            }
            yield f"data: {json.dumps(completion_data)}\n\n"

            logger.info(
                "Streaming synthesis completed",
                request_id=request_id,
                chunks=chunk_count,
                total_ms=total_duration * 1000,
                ttfa_ms=first_chunk_time * 1000 if first_chunk_time else 0
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Streaming synthesis failed",
                request_id=request_id,
                error=error_msg
            )
            # Send error event
            error_data = {"event": "error", "message": error_msg}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_chunks(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

# ============================================================================
# ENDPOINTS DE PRUEBA Y UTILIDADES
# ============================================================================

@app.get("/test/emotions")
async def test_emotions() -> dict:
    """Lista todas las emociones soportadas con sus marcadores Fish Audio."""
    try:
        from .voices.presets import get_emotion_marker_map
        emotion_map = get_emotion_marker_map()
        return {
            "ok": True,
            "emotions": list(emotion_map.keys()),
            "count": len(emotion_map),
            "markers": emotion_map
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "emotions": ["neutral", "happy", "sad", "angry", "surprised", "excited",
                        "confused", "upset", "fear", "asco", "love", "bored", "sleeping", "thinking"]
        }

@app.post("/test/quick")
async def test_quick(emotion: str = "neutral") -> SynthesizeOut:
    """Prueba rápida de síntesis con texto predeterminado.

    Args:
        emotion: Emoción a usar (default: neutral)

    Returns:
        Audio sintetizado en base64
    """
    test_text = "Esta es una prueba rápida del sistema de síntesis de voz."
    body = SynthesizeIn(text=test_text, emotion=emotion, backend="http")
    request = Request(scope={"type": "http", "client": ("127.0.0.1", 0), "headers": []})
    return await synthesize(body, request)

@app.get("/test/status")
async def test_status() -> dict:
    """Estado completo del sistema TTS.

    Returns:
        Estado detallado del servicio y Fish Audio backend
    """
    fish_healthy = False
    fish_error = None

    if engine_http is not None:
        try:
            fish_healthy = engine_http.health()
        except Exception as e:
            fish_error = str(e)

    return {
        "ok": True,
        "service": {
            "name": "vtuber-tts",
            "version": "0.4.0",
            "status": "running"
        },
        "backends": {
            "http": {
                "configured": engine_http is not None,
                "healthy": fish_healthy,
                "url": engine_http.url if engine_http else None,
                "error": fish_error
            },
            "local": {
                "configured": True,
                "status": "deprecated_stub"
            }
        },
        "features": {
            "emotions_count": 14,
            "max_text_length": 5000,
            "metrics_enabled": True,
            "voice_reference": os.getenv("FISH_REF_WAV") is not None
        }
    }

@app.post("/test/emotion/{emotion}")
async def test_emotion(emotion: str, text: str = None) -> SynthesizeOut:
    """Prueba una emoción específica con texto personalizado u predeterminado.

    Args:
        emotion: Emoción a probar
        text: Texto opcional (usa predeterminado si no se proporciona)

    Returns:
        Audio sintetizado en base64
    """
    if text is None:
        # Textos predeterminados según emoción
        emotion_texts = {
            "neutral": "Este es un mensaje con tono neutral.",
            "happy": "¡Qué alegría! ¡Estoy muy feliz de verte!",
            "sad": "Me siento un poco triste hoy...",
            "angry": "¡Esto es inaceptable! ¡Estoy muy molesta!",
            "surprised": "¡Oh! ¡No me lo esperaba! ¡Qué sorpresa!",
            "excited": "¡Esto es increíble! ¡Estoy tan emocionada!",
            "confused": "Hmm... no estoy muy segura de esto...",
            "upset": "Estoy algo disgustada con esto.",
            "fear": "¡Ten cuidado! ¡Esto me da miedo!",
            "asco": "Ugh, esto es realmente desagradable.",
            "love": "Te quiero mucho, eres muy especial para mí.",
            "bored": "Esto es tan aburrido... suspiro.",
            "sleeping": "Mmm... tengo tanto sueño... zzz.",
            "thinking": "Déjame pensar en esto cuidadosamente..."
        }
        text = emotion_texts.get(emotion, f"Probando la emoción {emotion}.")

    body = SynthesizeIn(text=text, emotion=emotion, backend="http")
    request = Request(scope={"type": "http", "client": ("127.0.0.1", 0), "headers": []})
    return await synthesize(body, request)

@app.get("/test/voices")
async def test_voices() -> dict:
    """Información sobre la configuración de voz de referencia."""
    return {
        "ok": True,
        "reference": {
            "wav_file": os.getenv("FISH_REF_WAV"),
            "text": os.getenv("FISH_REF_TXT"),
            "id": os.getenv("FISH_REF_ID"),
            "memory_cache": os.getenv("FISH_USE_MEMORY_CACHE") == "on"
        }
    }


@app.post("/test/benchmark")
async def test_benchmark(
    emotion: str = "neutral",
    text: Optional[str] = None,
    iterations: int = 1
) -> dict:
    """
    Benchmark endpoint para medir rendimiento de síntesis.

    Ejecuta múltiples iteraciones de síntesis y retorna métricas de rendimiento.

    Args:
        emotion: Emoción a usar (default: neutral)
        text: Texto personalizado (opcional, usa texto predeterminado si no se provee)
        iterations: Número de iteraciones (default: 1, max: 10)

    Returns:
        Métricas de rendimiento incluyendo tiempos, tamaños y estadísticas
    """
    import time
    import statistics

    # Validar iterations
    if iterations < 1 or iterations > 10:
        return {
            "ok": False,
            "error": "iterations must be between 1 and 10"
        }

    # Texto predeterminado si no se provee
    default_texts = {
        "neutral": "Este es un texto de prueba con emoción neutral para el benchmark.",
        "happy": "¡Qué alegría! ¡Estoy muy feliz de realizar este benchmark!",
        "sad": "Me siento un poco triste al realizar estas pruebas...",
        "angry": "¡Esto es inaceptable! ¡Necesitamos mejores tiempos de respuesta!",
    }

    test_text = text or default_texts.get(emotion, default_texts["neutral"])

    results = []

    for i in range(iterations):
        start_time = time.perf_counter()

        try:
            # Realizar síntesis
            body = SynthesizeIn(text=test_text, emotion=emotion, backend="http")
            request = Request(scope={"type": "http", "client": ("127.0.0.1", 0), "headers": []})
            response = await synthesize(body, request)

            duration = time.perf_counter() - start_time

            # Calcular tamaño de audio
            audio_size = len(response.audio_b64.encode()) if response.audio_b64 else 0

            results.append({
                "iteration": i + 1,
                "success": response.ok,
                "duration": duration,
                "audio_size_bytes": audio_size,
                "text_length": len(test_text)
            })

        except Exception as e:
            duration = time.perf_counter() - start_time
            results.append({
                "iteration": i + 1,
                "success": False,
                "duration": duration,
                "error": str(e)
            })

    # Calcular estadísticas
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    durations = [r["duration"] for r in successful]
    audio_sizes = [r["audio_size_bytes"] for r in successful]

    summary = {
        "ok": True,
        "benchmark": {
            "emotion": emotion,
            "text": test_text,
            "text_length": len(test_text),
            "iterations": iterations,
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / iterations * 100 if iterations > 0 else 0
        },
        "timing": {
            "avg_duration": statistics.mean(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "total_duration": sum(durations) if durations else 0
        },
        "audio": {
            "avg_size_bytes": statistics.mean(audio_sizes) if audio_sizes else 0,
            "avg_size_kb": statistics.mean(audio_sizes) / 1024 if audio_sizes else 0
        },
        "results": results
    }

    return summary


@app.post("/synthesize-stream")
async def synthesize_stream(data: SynthesizeIn):
    """
    Sintetiza audio en modo streaming para conversaciones en tiempo real.

    Retorna chunks de audio conforme se van generando (Server-Sent Events).
    Optimizado para baja latencia: primera respuesta en ~3-5 segundos.

    Formato de respuesta:
    - event: audio_chunk
    - data: {"index": 0, "audio_b64": "...", "text": "...", "emotion": "...", "duration_ms": 123}

    - event: complete
    - data: {"total_chunks": 5, "total_duration_ms": 45000, "predictor_stats": {...}}
    """
    if conversation_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation TTS engine not available. Check server logs."
        )

    from fastapi.responses import StreamingResponse
    import json

    async def generate_sse():
        """Generator function for Server-Sent Events."""
        try:
            chunk_count = 0
            total_duration = 0.0

            # Stream audio chunks
            async for audio_chunk in conversation_engine.synthesize_streaming(
                text=data.text,
                emotion=data.emotion
            ):
                # Convertir audio a base64
                audio_b64 = base64.b64encode(audio_chunk.audio_bytes).decode('utf-8')

                # Crear evento SSE
                event_data = {
                    "index": audio_chunk.sentence_index,
                    "audio_b64": audio_b64,
                    "text": audio_chunk.text,
                    "emotion": audio_chunk.emotion,
                    "duration_ms": round(audio_chunk.duration_ms, 2)
                }

                yield f"event: audio_chunk\n"
                yield f"data: {json.dumps(event_data)}\n\n"

                chunk_count += 1
                total_duration += audio_chunk.duration_ms

            # Evento de finalización con estadísticas
            completion_data = {
                "total_chunks": chunk_count,
                "total_duration_ms": round(total_duration, 2),
                "predictor_stats": conversation_engine.get_predictor_stats()
            }

            yield f"event: complete\n"
            yield f"data: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming synthesis: {e}")
            error_data = {"error": str(e)}
            yield f"event: error\n"
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/conversation/stats")
async def get_conversation_stats():
    """
    Obtiene estadísticas del motor de conversación (predictor, caché, etc).
    """
    if conversation_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation TTS engine not available"
        )

    return {
        "ok": True,
        "predictor": conversation_engine.get_predictor_stats(),
        "cache_size": len(conversation_engine.cache)
    }


@app.post("/conversation/cache/clear")
async def clear_conversation_cache():
    """Limpia el caché de frases del motor de conversación."""
    if conversation_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation TTS engine not available"
        )

    conversation_engine.clear_cache()

    return {
        "ok": True,
        "message": "Cache cleared successfully"
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8802)
