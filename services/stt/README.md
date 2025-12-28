# STT Service (Speech-to-Text)

Servicio de reconocimiento de voz en tiempo real para la VTuber Casiopy. Convierte audio en texto usando Whisper y está preparado para identificación de hablantes.

## Descripción

Este servicio proporciona:
- **Transcripción en tiempo real** de audio a texto usando Faster Whisper
- **Detección de actividad de voz** (VAD - Voice Activity Detection)
- **Arquitectura preparada** para identificación de hablantes (speaker identification)
- **API REST** para transcripción de archivos de audio
- **WebSocket** para streaming de audio en tiempo real (futuro)

## Arquitectura

```
┌─────────────────────────────────────────┐
│         STT Service (Port 8806)         │
│                                         │
│  ┌────────────────┐  ┌───────────────┐ │
│  │  Whisper STT   │  │   Speaker     │ │
│  │  (faster-      │  │  Identifier   │ │
│  │   whisper)     │  │  (Future)     │ │
│  └────────┬───────┘  └───────────────┘ │
│           │                             │
│  ┌────────▼─────────┐                  │
│  │   FastAPI REST   │                  │
│  │   /transcribe    │                  │
│  │   /health        │                  │
│  └──────────────────┘                  │
└─────────────────────────────────────────┘
           │
           ▼
    Gateway / Conversation
```

## Características Principales

### 1. **Transcripción de Audio**
- Soporta múltiples formatos: WAV, MP3, OGG, FLAC
- Modelo Whisper optimizado (faster-whisper)
- Detección automática de idioma o forzado a español
- Timestamps opcionales para cada palabra

### 2. **Voice Activity Detection (VAD)**
- Detecta cuándo hay voz en el audio
- Filtra silencios y ruido de fondo
- Reduce procesamiento innecesario

### 3. **Speaker Identification (Futuro)**
- Módulo preparado para identificar quién está hablando
- Embeddings de voz para comparación
- Base de datos de voces conocidas
- Clustering de hablantes desconocidos

## Instalación

### Requisitos
- Python 3.10+
- CUDA 11.8+ (opcional, para GPU acceleration)
- ~2GB de espacio para modelos Whisper

### Instalar Dependencias

```bash
cd services/stt
pip install -e .

# Para desarrollo
pip install -e ".[dev]"
```

## Uso

### Iniciar el Servicio

```bash
# Desde la raíz del proyecto
python -m uvicorn services.stt.src.server:app --host 127.0.0.1 --port 8806

# O usando el venv del proyecto
../../venv/Scripts/python.exe -m uvicorn src.server:app --host 127.0.0.1 --port 8806
```

### Variables de Entorno

```bash
# Modelo Whisper a usar (tiny, base, small, medium, large-v3)
export WHISPER_MODEL="base"

# Device (cpu, cuda, auto)
export DEVICE="auto"

# Idioma (es, en, auto)
export LANGUAGE="es"

# Puerto del servicio
export STT_PORT=8806
```

## API Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "ok": true,
  "service": "stt-service",
  "status": "running",
  "model": "base",
  "device": "cuda"
}
```

### Transcribir Audio
```http
POST /transcribe
Content-Type: multipart/form-data

file: <audio_file>
language: "es" (optional)
include_timestamps: false (optional)
```

**Response:**
```json
{
  "text": "Hola, ¿cómo estás?",
  "language": "es",
  "duration": 2.5,
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hola, ¿cómo estás?"
    }
  ],
  "speaker_id": null
}
```

### Identificar Hablante (Futuro)
```http
POST /identify-speaker
Content-Type: multipart/form-data

file: <audio_file>
```

**Response:**
```json
{
  "speaker_id": "user_001",
  "speaker_name": "Richard",
  "confidence": 0.92,
  "is_known": true
}
```

## Integración con el Ecosistema

### Flujo de Conversación de Voz

```
┌──────────────┐
│   Usuario    │
│   (habla)    │
└──────┬───────┘
       │ audio
       ▼
┌──────────────┐
│ STT Service  │
│              │
│ Whisper →    │
│   "Hola"     │
└──────┬───────┘
       │ text
       ▼
┌──────────────┐      ┌─────────────┐
│ Conversation │──────►│  Gateway    │
│   Service    │      │             │
│              │      │ broadcast   │
│ Response:    │◄─────│ emotion     │
│ "¡Hola!"     │      │ utterance   │
└──────┬───────┘      └─────────────┘
       │ text                │
       ▼                     ▼
┌──────────────┐      ┌─────────────┐
│ TTS Service  │      │ Face Service│
│              │      │             │
│ Audio output │      │ Show text   │
└──────────────┘      └─────────────┘
```

## Detalles Técnicos

### Faster Whisper

Faster Whisper es una reimplementación optimizada de Whisper usando CTranslate2:
- **4x más rápido** que el Whisper original
- **Mismo accuracy** que el modelo original
- **Menos memoria VRAM** (~2GB vs ~6GB para large-v3)

### Modelos Disponibles

| Modelo | Parámetros | VRAM | Speed | Accuracy |
|--------|-----------|------|-------|----------|
| tiny   | 39M       | ~1GB | 32x   | ⭐⭐     |
| base   | 74M       | ~1GB | 16x   | ⭐⭐⭐   |
| small  | 244M      | ~2GB | 6x    | ⭐⭐⭐⭐ |
| medium | 769M      | ~5GB | 2x    | ⭐⭐⭐⭐⭐ |
| large-v3 | 1550M   | ~10GB| 1x    | ⭐⭐⭐⭐⭐ |

**Recomendado**: `base` para uso general, `small` para mejor accuracy

### Speaker Identification (Preparación Futura)

El servicio está preparado para agregar identificación de hablantes usando:

1. **Pyannote.audio**: Diarización de hablantes (separar quién habla cuándo)
2. **SpeechBrain**: Extracción de embeddings de voz
3. **Resemblyzer**: Comparación de similitud entre voces

**Arquitectura planeada:**
```python
# Módulo futuro: src/speaker_identifier.py
class SpeakerIdentifier:
    def __init__(self):
        self.embedding_model = load_speechbrain_model()
        self.known_speakers = {}  # speaker_id -> embedding

    def extract_embedding(self, audio_data):
        """Extrae embedding único de voz."""
        pass

    def identify(self, audio_data) -> Optional[str]:
        """Identifica al hablante comparando con base de datos."""
        pass

    def register_speaker(self, speaker_id, audio_samples):
        """Registra nueva voz en la base de datos."""
        pass
```

## Configuración

### Ajuste de Modelo

Editar `src/config.py`:
```python
WHISPER_MODEL = "base"  # tiny, base, small, medium, large-v3
DEVICE = "auto"         # auto, cpu, cuda
LANGUAGE = "es"         # es, en, auto
COMPUTE_TYPE = "int8"   # int8, float16, float32
```

### VAD (Voice Activity Detection)

```python
VAD_CONFIG = {
    "threshold": 0.5,      # Umbral de detección (0.0-1.0)
    "min_silence_ms": 300, # Silencio mínimo para separar frases
    "min_speech_ms": 250   # Duración mínima de habla válida
}
```

## Troubleshooting

### Error: "No se encuentra el modelo"
- Los modelos se descargan automáticamente la primera vez
- Verificar conexión a internet
- Verificar espacio en disco (~2GB)

### Transcripción muy lenta
- Usar GPU si está disponible (`DEVICE=cuda`)
- Reducir tamaño del modelo (`WHISPER_MODEL=tiny`)
- Usar `COMPUTE_TYPE=int8` para modelos más rápidos

### Audio no reconocido
- Verificar formato de audio (WAV PCM 16kHz recomendado)
- Verificar que el audio tiene voz audible
- Ajustar `VAD_CONFIG.threshold` si es muy sensible

### CUDA out of memory
- Usar modelo más pequeño
- Reducir batch size
- Usar CPU (`DEVICE=cpu`)

## Roadmap

- [x] Transcripción básica con Whisper
- [x] API REST con FastAPI
- [x] Health check endpoint
- [ ] WebSocket para streaming en tiempo real
- [ ] VAD integrado
- [ ] Speaker identification
- [ ] Base de datos de voces conocidas
- [ ] Auto-calibración de VAD según ruido ambiente
- [ ] Soporte para múltiples hablantes simultáneos
- [ ] Traducción en tiempo real (español ↔ inglés)

## Licencia

Parte del proyecto IA_Vtuber

---

**Nota**: Este servicio está optimizado para conversaciones cortas en tiempo real. Para transcripción de archivos largos, considerar usar batch processing.
