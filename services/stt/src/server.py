"""STT Service - FastAPI server for speech-to-text transcription."""
import logging
import tempfile
import os
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import soundfile as sf

from .config import STT_PORT, HOST, SPEAKER_ID_ENABLED
from .transcriber import Transcriber
from .speaker_identifier import SpeakerIdentifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="STT Service",
    description="Speech-to-Text service with speaker identification support",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
transcriber: Optional[Transcriber] = None
speaker_id: Optional[SpeakerIdentifier] = None
service_ready: bool = False  # Track if service is fully initialized


# Response models
class HealthResponse(BaseModel):
    ok: bool
    service: str
    status: str
    ready: bool  # New field to indicate if model is loaded
    model: str
    device: str
    speaker_id_enabled: bool
    message: Optional[str] = None  # Optional status message


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration: float
    segments: list
    speaker_id: Optional[str] = None
    speaker_confidence: Optional[float] = None


class SpeakerIdentificationResponse(BaseModel):
    speaker_id: str
    speaker_name: Optional[str] = None
    confidence: float
    is_known: bool


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize transcriber and speaker identification on startup."""
    global transcriber, speaker_id, service_ready

    logger.info("Starting STT Service...")
    service_ready = False

    try:
        # Initialize transcriber (this loads the Whisper model - may take time on first run)
        logger.info("Initializing Whisper transcriber (loading model, may take 1-2 minutes)...")
        transcriber = Transcriber()
        logger.info("Transcriber initialized successfully")

        # Initialize speaker identifier (if enabled)
        speaker_id = SpeakerIdentifier(enabled=SPEAKER_ID_ENABLED)
        if SPEAKER_ID_ENABLED:
            logger.info("Speaker identification enabled")
        else:
            logger.info("Speaker identification disabled")

        # Mark service as fully ready
        service_ready = True
        logger.info(f"STT Service READY on {HOST}:{STT_PORT}")

    except Exception as e:
        logger.error(f"Failed to initialize STT service: {e}", exc_info=True)
        service_ready = False
        raise


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with detailed status."""
    from .config import WHISPER_MODEL, DEVICE

    # Check if service is fully initialized
    if not service_ready or transcriber is None:
        return HealthResponse(
            ok=True,  # Service is up, but not ready
            service="stt-service",
            status="initializing",
            ready=False,
            model=WHISPER_MODEL,
            device=DEVICE,
            speaker_id_enabled=SPEAKER_ID_ENABLED,
            message="Loading Whisper model... Please wait 1-2 minutes"
        )

    # Service is fully ready
    return HealthResponse(
        ok=True,
        service="stt-service",
        status="running",
        ready=True,
        model=WHISPER_MODEL,
        device=DEVICE,
        speaker_id_enabled=SPEAKER_ID_ENABLED,
        message="Ready to transcribe"
    )


# Transcription endpoint
@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    include_timestamps: bool = Form(False),
    identify_speaker: bool = Form(False),
):
    """Transcribe audio file to text.

    Args:
        file: Audio file (WAV, MP3, OGG, FLAC)
        language: Language code (e.g., 'es', 'en') or None for auto-detect
        include_timestamps: Include word-level timestamps
        identify_speaker: Try to identify the speaker (if enabled)

    Returns:
        Transcription result with text, language, and optional speaker info
    """
    if transcriber is None:
        raise HTTPException(status_code=503, detail="Transcriber not ready")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check file extension
    valid_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {', '.join(valid_extensions)}"
        )

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_path = tmp_file.name
            content = await file.read()
            tmp_file.write(content)

        # Transcribe
        logger.info(f"Transcribing file: {file.filename} (language: {language or 'auto'})")
        result = transcriber.transcribe_file(
            tmp_path,
            language=language,
            include_timestamps=include_timestamps,
        )

        # Speaker identification (if requested and enabled)
        speaker_id_result = None
        speaker_confidence = None

        if identify_speaker and speaker_id and speaker_id.enabled:
            # Load audio for speaker identification
            audio, _ = sf.read(tmp_path, dtype="float32")
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            speaker_info = speaker_id.identify_speaker(audio)
            if speaker_info:
                speaker_id_result = speaker_info.get("speaker_id")
                speaker_confidence = speaker_info.get("confidence")

        # Clean up temp file
        os.unlink(tmp_path)

        logger.info(f"Transcription completed: '{result['text'][:50]}...'")

        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
            segments=result["segments"],
            speaker_id=speaker_id_result,
            speaker_confidence=speaker_confidence,
        )

    except Exception as e:
        # Clean up on error
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


# Speaker identification endpoint (future)
@app.post("/identify-speaker", response_model=SpeakerIdentificationResponse)
async def identify_speaker_endpoint(
    file: UploadFile = File(...),
):
    """Identify speaker from audio file.

    This endpoint is prepared for future implementation.
    Currently returns a placeholder response.

    Args:
        file: Audio file containing voice sample

    Returns:
        Speaker identification result
    """
    if not SPEAKER_ID_ENABLED:
        raise HTTPException(
            status_code=501,
            detail="Speaker identification is not enabled"
        )

    if speaker_id is None or not speaker_id.enabled:
        raise HTTPException(
            status_code=503,
            detail="Speaker identifier not ready"
        )

    # TODO: Implement actual speaker identification
    logger.warning("Speaker identification called but not fully implemented")

    return SpeakerIdentificationResponse(
        speaker_id="unknown",
        speaker_name=None,
        confidence=0.0,
        is_known=False,
    )


# Register speaker endpoint (future)
@app.post("/register-speaker")
async def register_speaker_endpoint(
    speaker_id_param: str = Form(...),
    speaker_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """Register a new speaker voice in the database.

    This endpoint is prepared for future implementation.

    Args:
        speaker_id_param: Unique speaker identifier
        speaker_name: Optional human-readable name
        file: Audio file with voice sample

    Returns:
        Success status
    """
    if not SPEAKER_ID_ENABLED:
        raise HTTPException(
            status_code=501,
            detail="Speaker identification is not enabled"
        )

    if speaker_id is None or not speaker_id.enabled:
        raise HTTPException(
            status_code=503,
            detail="Speaker identifier not ready"
        )

    # TODO: Implement speaker registration
    logger.warning(f"Speaker registration called for '{speaker_id_param}' but not implemented")

    return {
        "ok": False,
        "message": "Speaker registration not yet implemented"
    }


def main():
    """Run the STT service."""
    import uvicorn

    logger.info(f"Starting STT service on {HOST}:{STT_PORT}")

    uvicorn.run(
        app,
        host=HOST,
        port=STT_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
