"""
Audit Logger - Sistema de logging y auditoría para test-service
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from collections import deque

# Setup logging
SERVICE_ROOT = Path(__file__).parent.parent
LOGS_DIR = SERVICE_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure file logger
file_handler = logging.FileHandler(LOGS_DIR / "audit.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Configure console logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(console_formatter)

# Create logger
logger = logging.getLogger("test-service")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# In-memory log buffer for recent logs (max 100 entries)
recent_logs = deque(maxlen=100)


class AuditEvent:
    """Audit event structure."""

    def __init__(
        self,
        event_type: str,
        action: str,
        details: Dict[str, Any],
        duration_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.action = action
        self.details = details
        self.duration_ms = duration_ms
        self.success = success
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "event_type": self.event_type,
            "action": self.action,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "success": self.success,
            "error": self.error
        }

    def log(self):
        """Log the event."""
        log_data = self.to_dict()

        # Add to recent logs buffer
        recent_logs.append(log_data)

        # Format message
        msg_parts = [f"[{self.event_type}] {self.action}"]

        if self.duration_ms:
            msg_parts.append(f"({self.duration_ms:.2f}ms)")

        if self.details:
            details_str = " | ".join(f"{k}={v}" for k, v in self.details.items())
            msg_parts.append(f"| {details_str}")

        if self.error:
            msg_parts.append(f"| ERROR: {self.error}")

        message = " ".join(msg_parts)

        # Log to file and console
        if self.success:
            logger.info(message)
        else:
            logger.error(message)

        # Also write to JSON log
        json_log_path = LOGS_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.json"
        try:
            # Append to daily JSON log
            with open(json_log_path, "a", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            logger.error(f"Failed to write JSON log: {e}")


def log_tts_synthesis(
    text: str,
    emotion: str,
    duration_ms: float,
    audio_size_kb: float,
    filename: str,
    success: bool = True,
    error: Optional[str] = None
):
    """Log TTS synthesis event."""
    event = AuditEvent(
        event_type="TTS_SYNTHESIS",
        action="generate_audio",
        details={
            "text_length": len(text),
            "emotion": emotion,
            "audio_size_kb": round(audio_size_kb, 2),
            "filename": filename,
            "chars_per_second": round(len(text) / (duration_ms / 1000), 2) if duration_ms > 0 else 0
        },
        duration_ms=duration_ms,
        success=success,
        error=error
    )
    event.log()


def log_service_action(
    service_id: str,
    action: str,
    duration_ms: float,
    success: bool = True,
    error: Optional[str] = None,
    **kwargs
):
    """Log service start/stop action."""
    event = AuditEvent(
        event_type="SERVICE_CONTROL",
        action=f"{action}_{service_id}",
        details=kwargs,
        duration_ms=duration_ms,
        success=success,
        error=error
    )
    event.log()


def log_api_request(
    endpoint: str,
    method: str,
    duration_ms: float,
    status_code: int,
    **kwargs
):
    """Log API request."""
    event = AuditEvent(
        event_type="API_REQUEST",
        action=f"{method} {endpoint}",
        details={"status_code": status_code, **kwargs},
        duration_ms=duration_ms,
        success=status_code < 400
    )
    event.log()


def get_recent_logs(limit: int = 50) -> list:
    """Get recent logs from buffer."""
    return list(recent_logs)[-limit:]


def get_logs_summary() -> Dict[str, Any]:
    """Get summary of logs."""
    if not recent_logs:
        return {
            "total_events": 0,
            "event_types": {},
            "success_rate": 0.0
        }

    event_types = {}
    successful = 0

    for log in recent_logs:
        event_type = log.get("event_type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1
        if log.get("success", False):
            successful += 1

    return {
        "total_events": len(recent_logs),
        "event_types": event_types,
        "success_rate": round((successful / len(recent_logs)) * 100, 2) if recent_logs else 0.0,
        "recent_count": len(recent_logs)
    }


def get_tts_metrics() -> Dict[str, Any]:
    """Get TTS-specific metrics from recent logs."""
    tts_logs = [log for log in recent_logs if log.get("event_type") == "TTS_SYNTHESIS"]

    if not tts_logs:
        return {
            "total_syntheses": 0,
            "avg_duration_ms": 0,
            "avg_chars_per_second": 0,
            "total_audio_size_kb": 0
        }

    durations = [log["duration_ms"] for log in tts_logs if log.get("duration_ms")]
    chars_per_sec = [
        log["details"]["chars_per_second"]
        for log in tts_logs
        if "details" in log and "chars_per_second" in log["details"]
    ]
    audio_sizes = [
        log["details"]["audio_size_kb"]
        for log in tts_logs
        if "details" in log and "audio_size_kb" in log["details"]
    ]

    return {
        "total_syntheses": len(tts_logs),
        "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
        "min_duration_ms": round(min(durations), 2) if durations else 0,
        "max_duration_ms": round(max(durations), 2) if durations else 0,
        "avg_chars_per_second": round(sum(chars_per_sec) / len(chars_per_sec), 2) if chars_per_sec else 0,
        "total_audio_size_kb": round(sum(audio_sizes), 2) if audio_sizes else 0
    }
