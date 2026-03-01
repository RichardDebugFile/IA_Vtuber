"""
Conftest para tests offline (sin servicios).

Anula require_service_running del conftest padre para que estos tests
puedan ejecutarse sin el memory-service levantado.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def require_service_running():
    """Override: los tests offline no necesitan el servicio."""
    pass  # sin chequeo de conectividad
