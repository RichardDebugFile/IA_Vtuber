# TTS Service Tools

Herramientas de diagnóstico y benchmark para el servicio TTS.

**IMPORTANTE:** Estos scripts NO son parte del código de producción. Son herramientas de desarrollo para testing, diagnóstico y benchmarking.

## Estructura

```
tools/
├── __init__.py           # Este módulo
├── README.md             # Esta documentación
├── benchmark.py          # Benchmark completo del servicio
├── probe_emotions.py     # Prueba de mapeo de emociones
├── probe_tts.py          # Diagnóstico de conexión TTS
├── diag.py               # Diagnósticos del sistema
└── performance.py        # Medición simple de performance
```

## Uso

### Benchmark Completo

Ejecuta pruebas de performance del servicio TTS con múltiples métricas.

```bash
# Quick test (3 emociones, 1 iteración)
python -m tools.benchmark --quick

# Full test (14 emociones, 5 iteraciones)
python -m tools.benchmark --full

# Custom test
python -m tools.benchmark --emotions neutral happy sad --iterations 3

# Stress test (múltiples longitudes de texto)
python -m tools.benchmark --stress

# Especificar URL y output
python -m tools.benchmark --url http://localhost:8802 --output results.json
```

**Métricas reportadas:**
- Success rate (%)
- Average/min/max duration
- P50/P95/P99 percentiles
- Requests per second
- Audio sizes

### Prueba de Emociones

Genera audios de prueba para cada emoción configurada.

```bash
python -m tools.probe_emotions
```

**Output:** Crea archivos WAV en `_out/emotions/` para cada emoción.

### Diagnóstico de Conexión TTS

Verifica que el servicio TTS esté funcionando correctamente.

```bash
python -m tools.probe_tts
```

**Verifica:**
- Conectividad al servicio
- Generación de audio exitosa
- Formato de audio correcto

### Diagnósticos del Sistema

Ejecuta diagnósticos completos del sistema TTS.

```bash
python -m tools.diag
```

**Verifica:**
- Dependencias instaladas
- Modelos disponibles
- Archivos de configuración
- Conectividad a servicios externos

### Medición de Performance

Herramienta simple para medir tiempo de generación end-to-end.

```bash
python -m tools.performance
```

## Requisitos

Todas las herramientas requieren que el servicio TTS esté corriendo:

```bash
# En otra terminal
python -m src.server
```

## Notas

- Los resultados de benchmark se guardan en `benchmark_results_TIMESTAMP.json`
- Los audios de prueba se guardan en `_out/` o `tests/outputs/`
- Para ejecutar desde raíz del proyecto, usar: `python -m services.tts.tools.benchmark`

## Troubleshooting

### Error: "Module not found"

```bash
# Asegurarse de estar en el directorio correcto
cd services/tts
python -m tools.benchmark
```

### Error: "Connection refused"

Verificar que el servidor TTS esté corriendo:

```bash
curl http://localhost:8802/test/status
```

### Error: "Import errors"

Verificar que las dependencias estén instaladas:

```bash
pip install -r requirements.txt
```
