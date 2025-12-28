"""
Monitoring System - Uptime tracking, alerting, and Docker monitoring
"""
from __future__ import annotations

import asyncio
import subprocess
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx


class ServiceState(str, Enum):
    """Service state enum."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


@dataclass
class ServiceMetrics:
    """Metrics for a single service."""
    service_id: str
    name: str
    current_state: ServiceState = ServiceState.UNKNOWN
    last_check: Optional[datetime] = None
    last_online: Optional[datetime] = None
    last_offline: Optional[datetime] = None

    # Uptime tracking
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0

    # Response time tracking (rolling window of last 100 checks)
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

    # State transitions
    state_changes: deque = field(default_factory=lambda: deque(maxlen=50))
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    # Alerts
    alert_triggered: bool = False
    last_alert_time: Optional[datetime] = None

    def update(self, state: ServiceState, response_time_ms: Optional[float] = None, error: Optional[str] = None):
        """Update metrics with new check result."""
        now = datetime.now()
        self.last_check = now
        self.total_checks += 1

        # Track state change
        if state != self.current_state:
            self.state_changes.append({
                "from": self.current_state.value,
                "to": state.value,
                "timestamp": now.isoformat(),
                "error": error
            })
            self.current_state = state

        # Update success/failure counts
        if state == ServiceState.ONLINE:
            self.successful_checks += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_online = now
            self.alert_triggered = False  # Clear alert when service recovers
        else:
            self.failed_checks += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_offline = now

        # Track response time
        if response_time_ms is not None:
            self.response_times.append(response_time_ms)

    @property
    def uptime_percentage(self) -> float:
        """Calculate uptime percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        p95_index = int(len(sorted_times) * 0.95)
        return sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]

    @property
    def uptime_duration(self) -> Optional[timedelta]:
        """Calculate how long the service has been continuously online."""
        if self.current_state == ServiceState.ONLINE and self.last_online:
            # Find last state change to offline
            for change in reversed(self.state_changes):
                if change["to"] == "offline" or change["to"] == "error":
                    last_down_time = datetime.fromisoformat(change["timestamp"])
                    return datetime.now() - last_down_time
            # If no offline found, been online since first check
            return datetime.now() - self.last_online
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        uptime_dur = self.uptime_duration
        return {
            "service_id": self.service_id,
            "name": self.name,
            "current_state": self.current_state.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_online": self.last_online.isoformat() if self.last_online else None,
            "last_offline": self.last_offline.isoformat() if self.last_offline else None,
            "uptime_percentage": round(self.uptime_percentage, 2),
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "avg_response_time_ms": round(self.avg_response_time, 2),
            "p95_response_time_ms": round(self.p95_response_time, 2),
            "recent_response_times": list(self.response_times)[-10:],
            "state_changes": list(self.state_changes)[-10:],
            "uptime_duration_seconds": uptime_dur.total_seconds() if uptime_dur else None,
            "alert_triggered": self.alert_triggered,
            "last_alert_time": self.last_alert_time.isoformat() if self.last_alert_time else None
        }


@dataclass
class Alert:
    """Alert for service issue."""
    service_id: str
    alert_type: str  # "service_down", "slow_response", "repeated_failures"
    severity: str  # "warning", "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_id": self.service_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


class MonitoringSystem:
    """Centralized monitoring system for all services."""

    def __init__(self):
        self.metrics: Dict[str, ServiceMetrics] = {}
        self.alerts: deque = deque(maxlen=100)  # Keep last 100 alerts
        self.alert_thresholds = {
            "consecutive_failures": 3,  # Alert after 3 consecutive failures
            "slow_response_ms": 5000,   # Alert if response > 5 seconds
            "alert_cooldown_minutes": 5  # Don't re-alert for same service within 5 minutes
        }

    def register_service(self, service_id: str, name: str):
        """Register a service for monitoring."""
        if service_id not in self.metrics:
            self.metrics[service_id] = ServiceMetrics(service_id=service_id, name=name)

    def update_service(
        self,
        service_id: str,
        state: ServiceState,
        response_time_ms: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Update service metrics and check for alerts."""
        if service_id not in self.metrics:
            return

        metrics = self.metrics[service_id]
        metrics.update(state, response_time_ms, error)

        # Check for alert conditions
        self._check_alerts(service_id, metrics)

    def _check_alerts(self, service_id: str, metrics: ServiceMetrics):
        """Check if service should trigger an alert."""
        now = datetime.now()

        # Check cooldown - don't re-alert if we alerted recently
        if metrics.last_alert_time:
            cooldown = timedelta(minutes=self.alert_thresholds["alert_cooldown_minutes"])
            if now - metrics.last_alert_time < cooldown:
                return

        # Alert: Service down (consecutive failures)
        if metrics.consecutive_failures >= self.alert_thresholds["consecutive_failures"]:
            if not metrics.alert_triggered:
                alert = Alert(
                    service_id=service_id,
                    alert_type="service_down",
                    severity="critical",
                    message=f"Service '{metrics.name}' is DOWN ({metrics.consecutive_failures} consecutive failures)",
                    details={
                        "consecutive_failures": metrics.consecutive_failures,
                        "last_check": metrics.last_check.isoformat() if metrics.last_check else None,
                        "current_state": metrics.current_state.value
                    }
                )
                self.alerts.append(alert)
                metrics.alert_triggered = True
                metrics.last_alert_time = now

        # Alert: Slow response
        if metrics.response_times and metrics.current_state == ServiceState.ONLINE:
            recent_avg = sum(list(metrics.response_times)[-5:]) / min(5, len(metrics.response_times))
            if recent_avg > self.alert_thresholds["slow_response_ms"]:
                alert = Alert(
                    service_id=service_id,
                    alert_type="slow_response",
                    severity="warning",
                    message=f"Service '{metrics.name}' is responding slowly ({recent_avg:.0f}ms avg)",
                    details={
                        "avg_response_ms": round(recent_avg, 2),
                        "threshold_ms": self.alert_thresholds["slow_response_ms"]
                    }
                )
                self.alerts.append(alert)

    def get_service_metrics(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific service."""
        if service_id in self.metrics:
            return self.metrics[service_id].to_dict()
        return None

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all services."""
        return {
            service_id: metrics.to_dict()
            for service_id, metrics in self.metrics.items()
        }

    def get_recent_alerts(self, limit: int = 20, unresolved_only: bool = False) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        alerts_list = list(self.alerts)
        if unresolved_only:
            alerts_list = [a for a in alerts_list if not a.resolved]
        return [a.to_dict() for a in alerts_list[-limit:]]

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        total_services = len(self.metrics)
        online_services = sum(1 for m in self.metrics.values() if m.current_state == ServiceState.ONLINE)
        offline_services = sum(1 for m in self.metrics.values() if m.current_state == ServiceState.OFFLINE)
        error_services = sum(1 for m in self.metrics.values() if m.current_state == ServiceState.ERROR)

        # Calculate overall uptime
        total_checks = sum(m.total_checks for m in self.metrics.values())
        total_successful = sum(m.successful_checks for m in self.metrics.values())
        overall_uptime = (total_successful / total_checks * 100) if total_checks > 0 else 0.0

        # Count unresolved alerts
        unresolved_alerts = sum(1 for a in self.alerts if not a.resolved)

        return {
            "total_services": total_services,
            "online": online_services,
            "offline": offline_services,
            "error": error_services,
            "overall_uptime_percentage": round(overall_uptime, 2),
            "unresolved_alerts": unresolved_alerts,
            "health_status": "healthy" if online_services == total_services else "degraded" if online_services > 0 else "critical"
        }


class DockerMonitor:
    """Monitor Docker containers (specifically Fish Speech)."""

    @staticmethod
    async def check_container_status(container_name: str = "fish-speech-ngc") -> Dict[str, Any]:
        """Check Docker container status."""
        try:
            # Check if container exists and is running
            result = subprocess.run(
                f'docker ps -a --filter "name={container_name}" --format "{{{{.Status}}}}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                status_text = result.stdout.strip()
                is_running = "Up" in status_text

                return {
                    "exists": True,
                    "running": is_running,
                    "status_text": status_text,
                    "error": None
                }
            else:
                return {
                    "exists": False,
                    "running": False,
                    "status_text": None,
                    "error": "Container not found"
                }
        except subprocess.TimeoutExpired:
            return {
                "exists": False,
                "running": False,
                "status_text": None,
                "error": "Docker command timeout"
            }
        except Exception as e:
            return {
                "exists": False,
                "running": False,
                "status_text": None,
                "error": str(e)
            }

    @staticmethod
    async def get_container_stats(container_name: str = "fish-speech-ngc") -> Dict[str, Any]:
        """Get Docker container resource usage stats."""
        try:
            result = subprocess.run(
                f'docker stats {container_name} --no-stream --format "{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('|')
                if len(parts) == 2:
                    return {
                        "cpu_percent": parts[0].strip(),
                        "memory_usage": parts[1].strip(),
                        "error": None
                    }

            return {"cpu_percent": None, "memory_usage": None, "error": "Failed to parse stats"}
        except subprocess.TimeoutExpired:
            return {"cpu_percent": None, "memory_usage": None, "error": "Docker stats timeout"}
        except Exception as e:
            return {"cpu_percent": None, "memory_usage": None, "error": str(e)}

    @staticmethod
    async def get_gpu_stats() -> Dict[str, Any]:
        """Get GPU stats using nvidia-smi."""
        try:
            result = subprocess.run(
                'nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                parts = [p.strip() for p in result.stdout.strip().split(',')]
                if len(parts) == 4:
                    return {
                        "gpu_utilization_percent": float(parts[0]),
                        "memory_used_mb": float(parts[1]),
                        "memory_total_mb": float(parts[2]),
                        "temperature_celsius": float(parts[3]),
                        "memory_percent": round((float(parts[1]) / float(parts[2])) * 100, 2),
                        "error": None
                    }

            return {"error": "Failed to parse nvidia-smi output"}
        except subprocess.TimeoutExpired:
            return {"error": "nvidia-smi timeout"}
        except Exception as e:
            return {"error": str(e)}


# Global monitoring instance
monitoring = MonitoringSystem()
