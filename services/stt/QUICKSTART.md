# STT Service - Inicio Rápido

## Instalación

```bash
# Desde la raíz del proyecto
cd services/stt

# Instalar dependencias (ya instaladas en el venv)
../../venv/Scripts/python.exe -m pip install -e .
```

## Iniciar el Servicio

```bash
# Opción 1: Desde el directorio del servicio
cd services/stt
../../venv/Scripts/python.exe -m uvicorn src.server:app --host 127.0.0.1 --port 8803

# Opción 2: Desde el monitoring service
# Ir a http://127.0.0.1:8900 y hacer clic en "Start" en el servicio STT
```

## Probar el Servicio

### 1. Health Check

```bash
curl http://127.0.0.1:8803/health
```

Respuesta esperada:
```json
{
  "ok": true,
  "service": "stt-service",
  "status": "running",
  "model": "base",
  "device": "cuda",
  "speaker_id_enabled": false
}
```

### 2. Transcribir Audio (CLI)

```bash
# Verificar salud del servicio
../../venv/Scripts/python.exe -m src.cli health

# Transcribir un archivo de audio
../../venv/Scripts/python.exe -m src.cli transcribe path/to/audio.wav
```

### 3. Transcribir Audio (API)

```bash
# Usando curl
curl -X POST http://127.0.0.1:8803/transcribe \
  -F "file=@audio.wav" \
  -F "language=es" \
  -F "include_timestamps=false"
```

```python
# Usando Python
import httpx

with open("audio.wav", "rb") as f:
    files = {"file": ("audio.wav", f, "audio/wav")}
    data = {"language": "es", "include_timestamps": "false"}

    response = httpx.post(
        "http://127.0.0.1:8803/transcribe",
        files=files,
        data=data,
        timeout=60.0
    )

    result = response.json()
    print(result["text"])
```

## Configuración Rápida

### Variables de Entorno

```bash
# Modelo Whisper (tiny, base, small, medium, large-v3)
export WHISPER_MODEL=base

# Device (auto, cpu, cuda)
export DEVICE=auto

# Idioma por defecto (es, en, auto)
export LANGUAGE=es
```

### Modelos Recomendados

- **Para pruebas rápidas**: `tiny` (muy rápido, accuracy básico)
- **Uso general**: `base` (buen balance velocidad/accuracy)
- **Mejor accuracy**: `small` (más lento pero mejor)

## Formatos de Audio Soportados

- WAV (recomendado: PCM 16kHz mono)
- MP3
- OGG
- FLAC
- M4A
- WebM

## Troubleshooting

### "Model not found"
- Los modelos se descargan automáticamente la primera vez
- Requiere conexión a internet (~100-500MB según modelo)
- Se guardan en cache de HuggingFace (`~/.cache/huggingface/`)

### "Service too slow"
- Usar GPU si está disponible: `export DEVICE=cuda`
- Usar modelo más pequeño: `export WHISPER_MODEL=tiny`
- Verificar VRAM disponible con `nvidia-smi`

### "Connection refused"
- Verificar que el servicio está corriendo: `curl http://127.0.0.1:8803/health`
- Verificar puerto no esté en uso: `netstat -ano | findstr :8803`

## Próximos Pasos

1. **Integrar con Conversation Service**: Enviar transcripciones al conversation service
2. **WebSocket streaming**: Para transcripción en tiempo real
3. **Speaker identification**: Identificar quién está hablando
4. **VAD optimizado**: Mejor detección de voz vs silencio

## Ejemplos de Uso

Ver `tests/test_server.py` para ejemplos de uso con pytest.
