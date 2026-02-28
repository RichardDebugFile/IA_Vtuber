# TTS Blips - Dialogue Blips Generator

Microservicio para generar "dialogue blips" (sonidos cortos por letra/sílaba) con características de voz femenina para Casiopy, la IA VTuber.

## ¿Qué son los Dialogue Blips?

Los dialogue blips son sonidos sintéticos cortos que se reproducen por cada letra o sílaba mientras se muestra texto, similar a:
- **Undertale**: Sonidos únicos por personaje
- **Animal Crossing**: "Animalese" - blips por sílaba
- **Celeste**: Blips sintéticos por letra

## Características

✨ **Síntesis de voz femenina**:
- Frecuencia fundamental: 200-250 Hz (rango de voz femenina)
- Formantes ajustados para sonar como voz de mujer
- Modulación por emoción (pitch más alto=feliz, más bajo=triste)

🎵 **Generación por letra**:
- Un blip de ~50-80ms por cada letra
- Velocidad ajustable (blips/segundo)
- Pausa en espacios y puntuación

🎭 **Control emocional**:
- Pitch variable según emoción
- Intensidad ajustable
- Duración configurable

## Arquitectura

```
services/tts-blips/
├── src/
│   ├── blip_generator.py    # Generador de ondas sintéticas
│   ├── voice_config.py      # Configuración de voz femenina
│   ├── server.py            # API REST (FastAPI)
│   └── models.py            # Modelos Pydantic
├── audio_cache/             # Cache de blips generados
├── tests/                   # Tests unitarios
└── pyproject.toml
```

## API Endpoints

### `POST /blips/generate`
Genera una secuencia de blips para un texto dado.

**Request**:
```json
{
  "text": "Hola mundo",
  "emotion": "happy",
  "speed": 20.0,
  "volume": 0.7
}
```

**Response**:
```json
{
  "audio_b64": "UklGRiQAAABXQVZFZm10...",
  "duration_ms": 450,
  "num_blips": 9,
  "sample_rate": 44100
}
```

### `GET /blips/preview?char=a&emotion=neutral`
Genera un blip de preview para un carácter específico.

### `GET /health`
Health check del servicio.

## Uso

### Instalación
```bash
cd services/tts-blips
pip install -e .
```

### Desarrollo
```bash
python -m uvicorn src.server:app --reload --port 8802
```

### Testing
```bash
pytest tests/
```

## Configuración

Variables de entorno (`.env`):
```bash
BLIPS_PORT=8802
BLIPS_HOST=0.0.0.0
BLIPS_CACHE_ENABLED=true
BLIPS_FEMALE_PITCH=220  # Hz (rango femenino: 180-250)
```

## Integración con IA VTuber

El servicio puede usarse de dos formas:

### 1. Paralelo con TTS
```python
# Mientras TTS procesa
blips_audio = await blips_client.generate(text, emotion)
play_blips_until_tts_ready(blips_audio)
```

### 2. Fallback cuando TTS es lento
```python
if tts_latency > 2000:  # ms
    blips_audio = await blips_client.generate(text, emotion)
    play_blips(blips_audio)
```

## Parámetros de Voz Femenina

- **Frecuencia fundamental**: 200-250 Hz (vs 85-180 Hz masculina)
- **Formantes** (resonancias vocales):
  - F1: ~700 Hz (vs ~500 Hz masculina)
  - F2: ~1220 Hz (vs ~1000 Hz masculina)
  - F3: ~2600 Hz (vs ~2500 Hz masculina)
- **Duración**: 50-80ms por blip (más corto = más femenino)

## Modulación por Emoción

| Emoción | Pitch (Hz) | Duración (ms) | Intensidad |
|---------|-----------|---------------|------------|
| neutral | 220 | 60 | 0.7 |
| happy | 260 | 50 | 0.8 |
| sad | 180 | 80 | 0.5 |
| angry | 240 | 45 | 0.9 |
| excited | 280 | 40 | 0.85 |

## Licencia

Parte del proyecto IA_Vtuber.
