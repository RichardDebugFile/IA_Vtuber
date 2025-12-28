"""Pydantic models for TTS Blips API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BlipGenerateRequest(BaseModel):
    """Request model for generating blips."""

    text: str = Field(..., description="Text to generate blips for", min_length=1, max_length=1000)
    emotion: str = Field(default="neutral", description="Emotion for voice modulation")
    speed: float = Field(
        default=20.0,
        description="Blips per second (higher = faster speech)",
        ge=5.0,
        le=40.0,
    )
    volume: float = Field(
        default=0.7,
        description="Volume/amplitude (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )


class BlipGenerateResponse(BaseModel):
    """Response model for generated blips."""

    audio_b64: str = Field(..., description="Base64-encoded WAV audio")
    duration_ms: int = Field(..., description="Total duration in milliseconds")
    num_blips: int = Field(..., description="Number of blips generated")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")
    emotion: str = Field(..., description="Emotion used")
    text_length: int = Field(..., description="Length of input text")


class BlipPreviewResponse(BaseModel):
    """Response model for single blip preview."""

    audio_b64: str = Field(..., description="Base64-encoded WAV audio")
    char: str = Field(..., description="Character the blip represents")
    emotion: str = Field(..., description="Emotion used")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")
