# STT Service - Troubleshooting

## Error: "Requested int8 compute type not supported"

**Síntoma:**
```
ValueError: Requested int8 compute type, but the target device or backend do not support efficient int8 computation.
```

**Causa:**
El tipo de cómputo `int8` no es compatible con todas las GPUs/CPUs.

**Solución:**
El servicio ahora detecta automáticamente el mejor `compute_type`:
- **CUDA disponible**: Usa `float16` (compatible con GPUs modernas incluyendo Blackwell RTX 50xx)
- **Solo CPU**: Usa `float32`

Si quieres forzar un tipo específico:
```bash
export COMPUTE_TYPE=float16  # Para GPU
export COMPUTE_TYPE=float32  # Para CPU
```

## Error: "CUDA out of memory"

**Síntoma:**
```
RuntimeError: CUDA out of memory
```

**Solución:**
1. Usar modelo más pequeño:
   ```bash
   export WHISPER_MODEL=tiny
   ```

2. Cerrar otros procesos que usen VRAM

3. Usar CPU en lugar de GPU:
   ```bash
   export DEVICE=cpu
   ```

## Error: "Model download failed"

**Síntoma:**
El modelo no se descarga o falla en la primera ejecución.

**Solución:**
1. Verificar conexión a internet
2. Verificar espacio en disco (~500MB)
3. Descargar manualmente:
   ```python
   from faster_whisper import WhisperModel
   model = WhisperModel("base", device="cpu")
   ```

## GPU no detectada

**Síntoma:**
El servicio usa CPU cuando debería usar GPU.

**Verificación:**
```python
import torch
print(torch.cuda.is_available())  # Debe ser True
print(torch.cuda.get_device_name(0))  # Debe mostrar tu GPU
```

**Solución:**
1. Verificar drivers NVIDIA actualizados
2. Verificar instalación de CUDA:
   ```bash
   nvidia-smi
   ```
3. Para GPUs Blackwell (RTX 50xx), asegurarse de tener:
   - CUDA 12.x o superior
   - PyTorch con soporte CUDA 12

## Audio no reconocido

**Síntoma:**
La transcripción está vacía o es incorrecta.

**Solución:**
1. Verificar formato de audio (preferible: WAV PCM 16kHz)
2. Verificar que el audio tenga voz audible
3. Aumentar volumen del micrófono
4. Probar con archivo de audio conocido

## Transcripción muy lenta

**Solución:**
1. Verificar que use GPU:
   - En logs debe aparecer: "CUDA detected: using float16 compute type"
2. Usar modelo más pequeño:
   ```bash
   export WHISPER_MODEL=tiny
   ```
3. Verificar VRAM disponible:
   ```bash
   nvidia-smi
   ```

## Compatibilidad con GPUs modernas

### RTX 50xx (Blackwell)
- ✅ Soportado con `float16`
- ✅ Auto-detectado
- ✅ Requiere CUDA 12.x

### RTX 40xx (Ada Lovelace)
- ✅ Soportado con `float16`
- ✅ Auto-detectado

### RTX 30xx (Ampere)
- ✅ Soportado con `float16` o `int8`
- ✅ Auto-detectado

### Configuración Manual
Si la auto-detección falla:
```bash
export DEVICE=cuda
export COMPUTE_TYPE=float16
```

## Logs útiles

Para ver logs detallados:
```bash
# En el código
import logging
logging.basicConfig(level=logging.DEBUG)
```

El servicio muestra:
- `[INFO] src.transcriber: CUDA detected: using float16 compute type` → GPU detectada
- `[INFO] src.transcriber: CPU mode: using float32 compute type` → Modo CPU
- `[INFO] src.transcriber: Whisper model loaded successfully` → Modelo cargado OK

## Verificación rápida

```bash
# Health check
curl http://127.0.0.1:8806/health

# Debería retornar:
{
  "ok": true,
  "service": "stt-service",
  "status": "running",
  "model": "base",
  "device": "auto",
  "speaker_id_enabled": false
}
```
