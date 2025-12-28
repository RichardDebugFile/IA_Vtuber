"""Prometheus metrics for TTS service.

This module provides comprehensive metrics for monitoring:
- Request counts and latencies
- TTS synthesis performance
- Fish Audio server health
- Error rates and types
- Audio generation metrics (size, duration)
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional

# Service info
service_info = Info("tts_service", "TTS Service information")
service_info.info({
    "version": "0.4.0",
    "backend": "fish_audio",
    "description": "Text-to-Speech microservice"
})

# Request metrics
requests_total = Counter(
    "tts_requests_total",
    "Total number of TTS synthesis requests",
    ["backend", "emotion", "status"]
)

requests_in_progress = Gauge(
    "tts_requests_in_progress",
    "Number of TTS requests currently being processed"
)

# Latency metrics
synthesis_duration_seconds = Histogram(
    "tts_synthesis_duration_seconds",
    "Time spent synthesizing audio",
    ["backend", "emotion"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

request_duration_seconds = Histogram(
    "tts_request_duration_seconds",
    "Total request duration including overhead",
    ["backend", "emotion", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Audio generation metrics
audio_size_bytes = Histogram(
    "tts_audio_size_bytes",
    "Size of generated audio in bytes",
    ["backend", "emotion"],
    buckets=[1000, 5000, 10000, 50000, 100000, 500000, 1000000]
)

text_length_chars = Histogram(
    "tts_text_length_chars",
    "Length of input text in characters",
    ["backend", "emotion"],
    buckets=[10, 50, 100, 500, 1000, 5000]
)

# Error metrics
errors_total = Counter(
    "tts_errors_total",
    "Total number of errors",
    ["backend", "error_type", "emotion"]
)

retries_total = Counter(
    "tts_retries_total",
    "Total number of synthesis retries",
    ["backend", "reason"]
)

# Fish Audio backend metrics
fish_audio_health = Gauge(
    "tts_fish_audio_health",
    "Fish Audio server health status (1=healthy, 0=unhealthy)"
)

fish_audio_requests_total = Counter(
    "tts_fish_audio_requests_total",
    "Total requests to Fish Audio API",
    ["status"]
)

fish_audio_latency_seconds = Histogram(
    "tts_fish_audio_latency_seconds",
    "Fish Audio API response time",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Emotion distribution
emotion_distribution = Counter(
    "tts_emotion_distribution",
    "Distribution of emotions used",
    ["emotion"]
)

# Cache metrics (for Fish Audio memory cache)
cache_hits = Counter(
    "tts_cache_hits_total",
    "Number of cache hits for voice reference",
    ["cache_id"]
)

cache_misses = Counter(
    "tts_cache_misses_total",
    "Number of cache misses for voice reference",
    ["cache_id"]
)


def record_request(backend: str, emotion: str, status: str, duration_seconds: float):
    """Record a completed request.

    Args:
        backend: Backend used (http/local)
        emotion: Emotion used
        status: success/error
        duration_seconds: Total request duration
    """
    requests_total.labels(backend=backend, emotion=emotion, status=status).inc()
    request_duration_seconds.labels(backend=backend, emotion=emotion, status=status).observe(duration_seconds)


def record_synthesis(
    backend: str,
    emotion: str,
    duration_seconds: float,
    text_length: int,
    audio_size: Optional[int] = None
):
    """Record a synthesis operation.

    Args:
        backend: Backend used
        emotion: Emotion used
        duration_seconds: Synthesis duration
        text_length: Input text length
        audio_size: Generated audio size in bytes (optional)
    """
    synthesis_duration_seconds.labels(backend=backend, emotion=emotion).observe(duration_seconds)
    text_length_chars.labels(backend=backend, emotion=emotion).observe(text_length)
    emotion_distribution.labels(emotion=emotion).inc()

    if audio_size is not None:
        audio_size_bytes.labels(backend=backend, emotion=emotion).observe(audio_size)


def record_error(backend: str, error_type: str, emotion: str):
    """Record an error.

    Args:
        backend: Backend used
        error_type: Type of error (timeout, http_error, etc.)
        emotion: Emotion attempted
    """
    errors_total.labels(backend=backend, error_type=error_type, emotion=emotion).inc()


def record_retry(backend: str, reason: str):
    """Record a retry attempt.

    Args:
        backend: Backend used
        reason: Reason for retry (network_error, timeout, etc.)
    """
    retries_total.labels(backend=backend, reason=reason).inc()


def update_fish_health(healthy: bool):
    """Update Fish Audio health status.

    Args:
        healthy: True if Fish Audio is healthy
    """
    fish_audio_health.set(1 if healthy else 0)


def record_fish_request(status: str, latency_seconds: float):
    """Record a Fish Audio API request.

    Args:
        status: success/error/timeout
        latency_seconds: Request latency
    """
    fish_audio_requests_total.labels(status=status).inc()
    fish_audio_latency_seconds.observe(latency_seconds)


def record_cache_hit(cache_id: str):
    """Record a cache hit.

    Args:
        cache_id: Cache identifier
    """
    cache_hits.labels(cache_id=cache_id).inc()


def record_cache_miss(cache_id: str):
    """Record a cache miss.

    Args:
        cache_id: Cache identifier
    """
    cache_misses.labels(cache_id=cache_id).inc()


# Context managers for automatic metric recording
class RequestMetrics:
    """Context manager for tracking request metrics."""

    def __init__(self, backend: str, emotion: str):
        self.backend = backend
        self.emotion = emotion
        self.start_time = None

    def __enter__(self):
        import time
        requests_in_progress.inc()
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        requests_in_progress.dec()
        duration = time.time() - self.start_time
        status = "error" if exc_type else "success"
        record_request(self.backend, self.emotion, status, duration)


# Export all metrics
__all__ = [
    "service_info",
    "requests_total",
    "requests_in_progress",
    "synthesis_duration_seconds",
    "request_duration_seconds",
    "audio_size_bytes",
    "text_length_chars",
    "errors_total",
    "retries_total",
    "fish_audio_health",
    "fish_audio_requests_total",
    "fish_audio_latency_seconds",
    "emotion_distribution",
    "cache_hits",
    "cache_misses",
    "record_request",
    "record_synthesis",
    "record_error",
    "record_retry",
    "update_fish_health",
    "record_fish_request",
    "record_cache_hit",
    "record_cache_miss",
    "RequestMetrics",
]
