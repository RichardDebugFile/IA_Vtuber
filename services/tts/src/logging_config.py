"""Centralized logging configuration for TTS service using loguru.

This module sets up structured logging with:
- Console output with colors
- File rotation
- JSON formatting for production
- Request tracing with correlation IDs
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional
from loguru import logger

# Remove default handler
logger.remove()

# Determine log level from environment
LOG_LEVEL = os.getenv("TTS_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("TTS_LOG_FILE", "")
LOG_JSON = os.getenv("TTS_LOG_JSON", "false").lower() in ("true", "1", "yes")

# Console handler with colors (for development)
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
           "<level>{message}</level>",
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# File handler with rotation (if LOG_FILE is set)
if LOG_FILE:
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if LOG_JSON:
        # JSON format for production/parsing
        logger.add(
            log_path,
            level=LOG_LEVEL,
            format="{message}",
            serialize=True,  # JSON format
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=False,  # Don't expose code in production logs
        )
    else:
        # Human-readable format
        logger.add(
            log_path,
            level=LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
        )


def get_logger(name: str):
    """Get a logger instance bound to a specific module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance

    Example:
        >>> from logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting synthesis", text_length=42, emotion="happy")
    """
    return logger.bind(module=name)


def log_request(
    endpoint: str,
    method: str = "POST",
    *,
    request_id: Optional[str] = None,
    **context
):
    """Log an incoming request with context.

    Args:
        endpoint: API endpoint path
        method: HTTP method
        request_id: Optional correlation ID
        **context: Additional context (text_length, emotion, etc.)
    """
    log_context = {
        "endpoint": endpoint,
        "method": method,
        "request_id": request_id,
        **context
    }
    logger.info(f"Request received: {method} {endpoint}", **log_context)


def log_response(
    endpoint: str,
    status_code: int,
    duration_ms: float,
    *,
    request_id: Optional[str] = None,
    **context
):
    """Log a response with timing.

    Args:
        endpoint: API endpoint path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        request_id: Optional correlation ID
        **context: Additional context
    """
    log_context = {
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "request_id": request_id,
        **context
    }

    if status_code >= 500:
        logger.error(f"Response: {status_code} ({duration_ms:.2f}ms)", **log_context)
    elif status_code >= 400:
        logger.warning(f"Response: {status_code} ({duration_ms:.2f}ms)", **log_context)
    else:
        logger.info(f"Response: {status_code} ({duration_ms:.2f}ms)", **log_context)


def log_synthesis(
    text_length: int,
    emotion: str,
    backend: str,
    duration_ms: float,
    success: bool,
    *,
    request_id: Optional[str] = None,
    audio_size: Optional[int] = None,
    error: Optional[str] = None
):
    """Log a TTS synthesis operation.

    Args:
        text_length: Length of input text
        emotion: Emotion used
        backend: Backend used (http/local)
        duration_ms: Synthesis duration
        success: Whether synthesis succeeded
        request_id: Optional correlation ID
        audio_size: Size of generated audio in bytes
        error: Error message if failed
    """
    context = {
        "text_length": text_length,
        "emotion": emotion,
        "backend": backend,
        "duration_ms": duration_ms,
        "success": success,
        "request_id": request_id,
        "audio_size": audio_size,
        "error": error,
    }

    if success:
        logger.info(
            f"Synthesis complete: {text_length} chars, {emotion}, {duration_ms:.2f}ms",
            **context
        )
    else:
        logger.error(
            f"Synthesis failed: {text_length} chars, {emotion}, {error}",
            **context
        )


# Export configured logger
__all__ = ["logger", "get_logger", "log_request", "log_response", "log_synthesis"]
