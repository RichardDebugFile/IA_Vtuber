"""Pydantic models for dataset generation system."""

from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class AudioEntry(BaseModel):
    """Represents a single audio file entry in the dataset."""
    id: int
    filename: str  # e.g., "casiopy_0001" (without .wav extension)
    text: str
    status: Literal["pending", "generating", "completed", "error"]
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_kb: Optional[int] = None
    generated_at: Optional[datetime] = None
    retry_count: int = 0  # Number of times this entry has been retried
    emotion: Optional[str] = None  # Override emotion (auto-detected if None)


class GenerationConfig(BaseModel):
    """Configuration for dataset generation."""
    total_clips: int = 2000  # Default target
    parallel_workers: int = 2  # Balanced: 2 workers for longer phrases (14+ words avg)
    backend: Literal["http", "docker"] = "http"
    max_retries: int = 3  # Maximum automatic retries for failed entries
    # No emotion labels - model learns prosody from audio directly


class GenerationState(BaseModel):
    """Current state of the generation process."""
    status: Literal["idle", "running", "paused", "stopped", "completed"]
    current_index: int = 0
    total_clips: int = 0
    completed: int = 0
    failed: int = 0
    config: GenerationConfig
    entries: list[AudioEntry] = []


class WebSocketMessage(BaseModel):
    """WebSocket message format for real-time updates."""
    type: str  # "progress", "status", "entry_update", "error"
    data: dict


class ServiceStatus(BaseModel):
    """Status of external services (TTS, Fish Speech)."""
    tts_available: bool = False
    fish_available: bool = False
    last_checked: Optional[datetime] = None
