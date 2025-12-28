"""FastAPI server for TTS Blips service."""
from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.blip_generator import BlipGenerator
from src.models import (
    BlipGenerateRequest,
    BlipGenerateResponse,
    BlipPreviewResponse,
    HealthResponse,
)

# Configuration
SAMPLE_RATE = int(os.getenv("BLIPS_SAMPLE_RATE", "44100"))
VERSION = "0.1.0"

# Global generator instance
generator: BlipGenerator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global generator

    # Startup
    generator = BlipGenerator(sample_rate=SAMPLE_RATE)
    print(f"[BLIPS] Initialized BlipGenerator with sample_rate={SAMPLE_RATE}")

    yield

    # Shutdown
    generator = None
    print("[BLIPS] Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="TTS Blips",
    description="Dialogue blips generator with female voice characteristics",
    version=VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        sample_rate=SAMPLE_RATE,
    )


@app.post("/blips/generate", response_model=BlipGenerateResponse)
async def generate_blips(request: BlipGenerateRequest):
    """Generate dialogue blips for given text.

    Args:
        request: BlipGenerateRequest with text, emotion, speed, volume

    Returns:
        BlipGenerateResponse with base64-encoded WAV audio

    Raises:
        HTTPException: If generation fails
    """
    if generator is None:
        raise HTTPException(status_code=500, detail="Generator not initialized")

    try:
        # Generate blips
        wav_bytes, duration_ms, num_blips = generator.generate_text_blips(
            text=request.text,
            emotion=request.emotion,
            blips_per_second=request.speed,
            silence_duration_ms=100.0,
        )

        # Encode to base64
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

        return BlipGenerateResponse(
            audio_b64=audio_b64,
            duration_ms=duration_ms,
            num_blips=num_blips,
            sample_rate=SAMPLE_RATE,
            emotion=request.emotion,
            text_length=len(request.text),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate blips: {str(e)}",
        ) from e


@app.get("/blips/preview", response_model=BlipPreviewResponse)
async def preview_blip(
    char: str = Query(default="a", description="Character to preview", min_length=1, max_length=1),
    emotion: str = Query(default="neutral", description="Emotion for voice modulation"),
):
    """Generate a single blip for preview.

    Args:
        char: Character to generate blip for
        emotion: Emotion for voice modulation

    Returns:
        BlipPreviewResponse with base64-encoded WAV audio

    Raises:
        HTTPException: If generation fails
    """
    if generator is None:
        raise HTTPException(status_code=500, detail="Generator not initialized")

    try:
        # Generate single blip
        wav_bytes = generator.generate_single_blip(
            char=char,
            emotion=emotion,
        )

        # Encode to base64
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

        return BlipPreviewResponse(
            audio_b64=audio_b64,
            char=char,
            emotion=emotion,
            sample_rate=SAMPLE_RATE,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate preview blip: {str(e)}",
        ) from e


def main():
    import uvicorn

    port = int(os.getenv("BLIPS_PORT", "8804"))
    host = os.getenv("BLIPS_HOST", "0.0.0.0")

    print(f"[BLIPS] Starting server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )

if __name__ == "__main__":
    main()
