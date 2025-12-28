# Test Service - Nuevas Funcionalidades

## ✅ Implementaciones Completadas

### 1. Control de Servicios (Start/Stop)

Los servicios ahora pueden ser iniciados y detenidos directamente desde el test-service mediante la API:

**Iniciar un servicio:**
```bash
POST /api/services/{service_id}/start
```

Ejemplo:
```bash
curl -X POST http://127.0.0.1:8900/api/services/fish/start
```

Respuesta:
```json
{
  "ok": true,
  "service": "fish",
  "action": "start",
  "status": "online",
  "output": "Server arrancado (nuevo). URL: http://127.0.0.1:8080"
}
```

**Detener un servicio:**
```bash
POST /api/services/{service_id}/stop
```

#### Servicios Manejables

| Servicio | ID | Manejable | Requiere |
|----------|-----|-----------|----------|
| Fish Audio Server | `fish` | ✅ | - |
| TTS Service | `tts` | ✅ | fish |
| Conversation AI | `conversation` | ✅ | - |
| Gateway | `gateway` | ✅ | - |
| Assistant | `assistant` | ❌ | - |

**Nota**: TTS requiere que Fish Audio esté corriendo primero. El sistema valida esto automáticamente.

### 2. Gestión Especializada del Fish Server

El Fish Audio Server tiene comandos dedicados que son ejecutados correctamente:

- **Start**: `python -m src.fish_server --start`
- **Stop**: `python -m src.fish_server --stop`
- **Status**: `python -m src.fish_server --status`

El test-service detecta automáticamente si Fish ya está corriendo y no intenta iniciarlo de nuevo.

### 3. Outputs Centralizados

Todos los archivos generados ahora se guardan en una carpeta dentro del test-service con nomenclatura estandarizada.

**Ubicación:**
```
services/test-service/outputs/tts/
```

**Formato de nombres:**
```
tts_{timestamp}_{id}_{emotion}.wav
```

Ejemplo:
```
tts_20251218_201110_8283_happy.wav
```

Donde:
- `timestamp`: YYYYMMDD_HHMMSS
- `id`: Hash del texto + emoción (4 dígitos)
- `emotion`: Emoción utilizada

**Listar archivos generados:**
```bash
GET /api/outputs/tts
```

Respuesta:
```json
{
  "ok": true,
  "count": 1,
  "files": [
    {
      "filename": "tts_20251218_201110_8283_happy.wav",
      "size_kb": 131.11,
      "created": "2025-12-18 20:11:11",
      "path": "F:\\...\\outputs\\tts\\tts_20251218_201110_8283_happy.wav"
    }
  ]
}
```

**Descargar un archivo:**
```bash
GET /api/outputs/tts/{filename}
```

### 4. Síntesis con Auto-Save

El endpoint de síntesis ahora guarda automáticamente los archivos generados:

```bash
POST /api/tts/synthesize?text={texto}&emotion={emoción}&save=true
```

Parámetros:
- `text` (required): Texto a sintetizar
- `emotion` (optional, default: "neutral"): Emoción a usar
- `save` (optional, default: true): Si guardar el archivo

Respuesta incluye información del archivo guardado:
```json
{
  "audio_b64": "...",
  "mime": "audio/wav",
  "saved_to": "F:\\...\\outputs\\tts\\tts_20251218_201110_8283_happy.wav",
  "filename": "tts_20251218_201110_8283_happy.wav"
}
```

## 📁 Estructura de Directorios

```
IA_Vtuber/
├── services/
│   ├── test-service/
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   └── static/
│   │   └── outputs/      # ← NUEVO: Outputs dentro del test-service
│   │       └── tts/      # Archivos de audio generados
│   │           ├── tts_20251218_201110_8283_happy.wav
│   │           ├── tts_20251218_201443_9832_neutral.wav
│   │           └── ...
│   ├── tts/
│   ├── conversation/
│   └── gateway/
└── ...
```

## 🔧 Configuración Interna

### Rutas del Proyecto

El test-service usa rutas relativas al servicio:

```python
SERVICE_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = SERVICE_ROOT / "outputs"
TTS_OUTPUTS_DIR = OUTPUTS_DIR / "tts"

# Project root for venv
PROJECT_ROOT = SERVICE_ROOT.parent.parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
```

### Comandos de Inicio

Los comandos de inicio están configurados para ejecutarse desde la raíz del proyecto:

```python
SERVICES = {
    "fish": {
        "start_cmd": f'cd services/tts && "{VENV_PYTHON}" -m src.fish_server --start',
        "stop_cmd": f'cd services/tts && "{VENV_PYTHON}" -m src.fish_server --stop',
        "cwd": str(PROJECT_ROOT)
    },
    "tts": {
        "start_cmd": f'cd services/tts && "{VENV_PYTHON}" -m uvicorn src.server:app --host 127.0.0.1 --port 8802',
        "cwd": str(PROJECT_ROOT),
        "requires": ["fish"]  # ← Valida que Fish esté corriendo
    }
}
```

## 🎯 Casos de Uso

### Caso 1: Iniciar todo el stack TTS

```bash
# 1. Iniciar Fish Server
curl -X POST http://127.0.0.1:8900/api/services/fish/start

# 2. Esperar 2-3 segundos

# 3. Iniciar TTS Service (valida automáticamente que Fish esté up)
curl -X POST http://127.0.0.1:8900/api/services/tts/start
```

### Caso 2: Generar y guardar múltiples audios

```bash
# Generar varios audios con diferentes emociones
curl -X POST "http://127.0.0.1:8900/api/tts/synthesize?text=Hola&emotion=happy"
curl -X POST "http://127.0.0.1:8900/api/tts/synthesize?text=Adios&emotion=sad"
curl -X POST "http://127.0.0.1:8900/api/tts/synthesize?text=Wow&emotion=surprised"

# Listar todos los archivos generados
curl http://127.0.0.1:8900/api/outputs/tts
```

### Caso 3: Descargar un audio específico

```bash
# Listar archivos
FILES=$(curl -s http://127.0.0.1:8900/api/outputs/tts | jq -r '.files[0].filename')

# Descargar
curl -O http://127.0.0.1:8900/api/outputs/tts/$FILES
```

## ⚠️ Notas Importantes

1. **Dependencias entre servicios**: El sistema valida automáticamente que los servicios requeridos estén corriendo antes de iniciar otro servicio.

2. **Timeout de inicio**: Los comandos de inicio tienen un timeout de 30 segundos.

3. **Detección de estado**: Después de iniciar un servicio, el sistema espera 2 segundos y luego valida que esté realmente corriendo mediante un health check.

4. **Límite de archivos listados**: El endpoint `/api/outputs/tts` retorna máximo los 50 archivos más recientes.

5. **Auto-save por defecto**: Todos los audios generados se guardan automáticamente a menos que se especifique `save=false`.

## 🔜 Próximas Mejoras Sugeridas

- [ ] Botones Start/Stop en la UI del dashboard
- [ ] Indicador visual de servicios "manejables"
- [ ] Logs en tiempo real de los servicios
- [ ] Historial de audios generados en la UI de TTS
- [ ] Botón de "reproducir" archivos antiguos desde el historial
- [ ] Limpieza automática de archivos antiguos (retention policy)
- [ ] Restart automático de servicios caídos
- [ ] Notificaciones cuando un servicio se cae
