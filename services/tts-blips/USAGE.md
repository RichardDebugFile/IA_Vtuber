# Guía de Uso - TTS Blips

## Inicio Rápido

### 1. Instalación

```bash
cd services/tts-blips
pip install -e .
```

### 2. Iniciar el Servidor

```bash
python -m src.server
```

El servidor estará disponible en `http://localhost:8803`

### 3. Probar el Servicio

```bash
# Test rápido
python test_quick.py

# Ver documentación interactiva
# Abrir en navegador: http://localhost:8803/docs
```

---

## Uso desde Python

### Cliente Simple

```python
import asyncio
import base64
import httpx

async def generate_blips(text: str, emotion: str = "neutral"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8803/blips/generate",
            json={
                "text": text,
                "emotion": emotion,
                "speed": 20.0,  # blips per second
                "volume": 0.7,  # 0.0 to 1.0
            }
        )
        data = response.json()
        audio_bytes = base64.b64decode(data["audio_b64"])

        # Guardar audio
        with open("output.wav", "wb") as f:
            f.write(audio_bytes)

        print(f"Generated {data['num_blips']} blips in {data['duration_ms']}ms")

# Usar
asyncio.run(generate_blips("Hola mundo", "happy"))
```

---

## API Endpoints

### `POST /blips/generate`

Genera una secuencia de blips para un texto.

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
  "sample_rate": 44100,
  "emotion": "happy",
  "text_length": 10
}
```

**Parámetros**:
- `text` (str, required): Texto para generar blips (1-1000 caracteres)
- `emotion` (str, optional): Emoción para modular la voz (default: "neutral")
  - Opciones: neutral, happy, sad, excited, angry, fear, love, confused, thinking, etc.
- `speed` (float, optional): Blips por segundo (5.0 - 40.0, default: 20.0)
  - 10 = lento (lectura pausada)
  - 20 = normal (conversación)
  - 30 = rápido (emocionado)
- `volume` (float, optional): Volumen (0.0 - 1.0, default: 0.7)

---

### `GET /blips/preview`

Genera un blip individual para preview.

**Request**:
```
GET /blips/preview?char=a&emotion=neutral
```

**Response**:
```json
{
  "audio_b64": "UklGRiQAAABXQVZF...",
  "char": "a",
  "emotion": "neutral",
  "sample_rate": 44100
}
```

**Parámetros**:
- `char` (str, required): Carácter para generar blip (1 carácter)
- `emotion` (str, optional): Emoción (default: "neutral")

---

### `GET /health`

Health check del servicio.

**Response**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "sample_rate": 44100
}
```

---

## Características de Voz Femenina

El generador usa parámetros acústicos optimizados para sonar como voz femenina:

| Parámetro | Valor Femenino | Valor Masculino (ref) |
|-----------|----------------|----------------------|
| **Pitch base** | 220 Hz | 120 Hz |
| **Rango de pitch** | 180-280 Hz | 85-180 Hz |
| **Formante F1** | ~700 Hz | ~500 Hz |
| **Formante F2** | ~1220 Hz | ~1000 Hz |
| **Formante F3** | ~2600 Hz | ~2500 Hz |
| **Duración blip** | 50-80 ms | 70-100 ms |

---

## Modulación por Emoción

Cada emoción modula el pitch, duración e intensidad del blip:

| Emoción | Pitch (Hz) | Duración (ms) | Amplitud | Descripción |
|---------|-----------|---------------|----------|-------------|
| **neutral** | 220 | 60 | 0.7 | Voz normal, balanceada |
| **happy** | 260 | 50 | 0.8 | Más agudo, rápido, energético |
| **excited** | 280 | 40 | 0.85 | Muy agudo, muy rápido |
| **love** | 240 | 70 | 0.7 | Agudo, suave, cálido |
| **sad** | 180 | 80 | 0.5 | Grave, lento, bajo volumen |
| **angry** | 240 | 45 | 0.9 | Tenso, staccato, fuerte |
| **fear** | 250 | 55 | 0.75 | Agudo, tembloroso |
| **thinking** | 210 | 70 | 0.6 | Ligeramente grave, pausado |
| **confused** | 230 | 65 | 0.6 | Variable, hesitante |
| **bored** | 190 | 75 | 0.5 | Grave, monótono, bajo |

---

## Integración con IA VTuber

### Caso 1: Blips Paralelos (Recomendado)

Reproduce blips mientras el TTS procesa en background:

```python
import asyncio
from blips_client import BlipsClient
from tts_client import TTSClient

async def speak_with_blips(text: str, emotion: str):
    blips = BlipsClient()
    tts = TTSClient()

    # 1. Generar blips inmediatamente
    blips_audio = await blips.generate(text, emotion)

    # 2. Iniciar TTS en background
    tts_task = asyncio.create_task(tts.synthesize(text, emotion))

    # 3. Reproducir blips
    play_audio(blips_audio)

    # 4. Cuando TTS termine, cambiar a audio real
    tts_audio = await tts_task
    stop_blips()
    play_audio(tts_audio)
```

### Caso 2: Fallback cuando TTS es Lento

```python
async def speak_with_fallback(text: str, emotion: str):
    tts = TTSClient()
    blips = BlipsClient()

    # Intentar TTS primero
    tts_task = asyncio.create_task(tts.synthesize(text, emotion))

    try:
        # Esperar máximo 2 segundos
        tts_audio = await asyncio.wait_for(tts_task, timeout=2.0)
        play_audio(tts_audio)
    except asyncio.TimeoutError:
        # TTS lento -> usar blips
        blips_audio = await blips.generate(text, emotion)
        play_audio(blips_audio)

        # TTS seguirá procesando en background
        tts_audio = await tts_task
        # Guardar para siguiente vez (cache)
```

---

## Variables de Entorno

Crear archivo `.env` en `services/tts-blips/`:

```bash
# Puerto del servicio
BLIPS_PORT=8803

# Host (0.0.0.0 para acceso externo)
BLIPS_HOST=0.0.0.0

# Sample rate (44100 recomendado)
BLIPS_SAMPLE_RATE=44100
```

---

## Testing

### Tests Unitarios

```bash
cd services/tts-blips
pytest tests/ -v
```

### Test Rápido con Audio

```bash
python test_quick.py
# Genera archivos .wav en test_outputs/
```

### Ejemplos de Integración

```bash
# Primero iniciar el servidor
python -m src.server

# En otra terminal, correr ejemplos
python example_integration.py
```

---

## Performance

| Métrica | Valor |
|---------|-------|
| **Latencia** | ~50-100ms (texto corto) |
| **Throughput** | ~100 requests/s |
| **Tamaño audio** | ~5-10 KB por segundo de audio |
| **CPU usage** | Bajo (<5% por request) |
| **Memoria** | ~50 MB |

---

## Troubleshooting

### El servidor no inicia

```bash
# Verificar que el puerto 8803 esté libre
netstat -ano | findstr :8803

# Cambiar puerto si es necesario
BLIPS_PORT=8804 python -m src.server
```

### Audio sin sonido o muy bajo

- Aumentar el parámetro `volume` en la request
- Verificar que el archivo .wav se haya generado correctamente
- Probar con `start test_outputs/text_happy.wav` en Windows

### Blips suenan masculinos

- El pitch base es 220 Hz (femenino). Si suena masculino, puede ser:
  - Problema con el reproductor de audio
  - Emoción "sad" o "bored" (pitch bajo)

---

## Roadmap

Futuras mejoras planeadas:

- [ ] Cache de blips pre-generados por carácter
- [ ] Soporte para múltiples voces (niña, mujer adulta, anciana)
- [ ] Variación de blips por vocal (a/e/i/o/u diferentes)
- [ ] Streaming de blips en tiempo real
- [ ] Integración con WebSocket para sincronización con subtítulos
- [ ] Efectos de audio (reverb, pitch shift dinámico)

---

## Créditos

Inspirado por sistemas de dialogue blips de:
- **Undertale** - Toby Fox
- **Animal Crossing** - Nintendo
- **Celeste** - Maddy Makes Games

Síntesis basada en investigación de fonética acústica para voces sintéticas femeninas.
