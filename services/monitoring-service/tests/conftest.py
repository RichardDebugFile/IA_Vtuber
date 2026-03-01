"""
Configuración compartida para los tests del monitoring-service.

Los tests de integración (TestMemoryRoute) requieren que el servicio esté corriendo:
  start.bat  → API en http://127.0.0.1:8900

Los tests unitarios (TestMemoryHtmlFile, TestMonitoringNavLink) no requieren
ningún servicio externo y siempre se ejecutan.

Ejecutar:
  cd services/monitoring-service
  python -m pytest tests/ -v
"""

import pytest
import httpx
from pathlib import Path

MONITORING_URL = "http://127.0.0.1:8900"
STATIC_DIR = Path(__file__).parent.parent / "src" / "static"


@pytest.fixture(scope="session")
def http_client():
    """Cliente HTTP apuntando al monitoring-service (si está corriendo)."""
    with httpx.Client(base_url=MONITORING_URL, timeout=5.0) as c:
        yield c


@pytest.fixture(scope="session")
def monitoring_available(http_client):
    """
    Devuelve True si el monitoring-service está corriendo, False si no.
    Los tests que usen este fixture se saltan automáticamente cuando no está disponible.
    """
    try:
        r = http_client.get("/health")
        return r.status_code == 200
    except httpx.ConnectError:
        return False
