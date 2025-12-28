"""
TTS Service Tools

Herramientas de diagnóstico, benchmark y pruebas para el servicio TTS.
Estos scripts NO son parte del código de producción.

Uso:
    python -m tools.benchmark --quick
    python -m tools.probe_emotions
    python -m tools.diag
    python -m tools.probe_tts

Disponibles:
    - benchmark.py: Benchmark completo del servicio con múltiples métricas
    - probe_emotions.py: Prueba de mapeo de emociones
    - probe_tts.py: Diagnóstico de conexión TTS
    - diag.py: Diagnósticos completos del sistema
    - performance.py: Medición simple de performance
"""

__all__ = [
    "benchmark",
    "probe_emotions",
    "probe_tts",
    "diag",
    "performance",
]
