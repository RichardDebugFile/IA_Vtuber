# Monitoring Service Dashboard

Sistema completo de monitoreo y control de todos los microservicios del proyecto IA VTuber.

## Características

### 🎯 Sistema de Monitoreo Avanzado v2.0
- ✅ **WebSocket en tiempo real** - Actualizaciones cada 5 segundos sin refresh
- ✅ **Métricas de Uptime** - Tracking histórico de disponibilidad
- ✅ **Sistema de Alertas** - Notificaciones automáticas de fallos
- ✅ **Monitoreo de Docker** - Estado y recursos del contenedor Fish Speech
- ✅ **GPU Monitoring** - Utilización, VRAM, temperatura vía nvidia-smi
- ✅ **Response Time Charts** - Visualización de latencias
- ✅ **Health Dashboard** - Estado general del sistema

### ⚡ Control de Servicios (NUEVO)
- ✅ **Iniciar/Detener/Reiniciar Docker** - Control completo del contenedor Fish Speech
- ✅ **Iniciar/Detener/Reiniciar TTS** - Gestión del servicio TTS
- ✅ **Control de otros servicios** - Gateway, Conversation, Assistant
- ✅ **Interfaz visual** - Botones de control en dashboard
- ✅ **Feedback en tiempo real** - Loading indicators y confirmaciones

### Dashboard Principal
- ✅ Monitoreo en tiempo real del estado de todos los servicios
- ✅ Health checks automáticos cada 5 segundos
- ✅ Visualización de puertos y tiempos de respuesta
- ✅ Indicadores visuales de estado (Online/Offline/Error)
- ✅ Barras de progreso con colores personalizados por servicio

### TTS Testing
- ✅ Interfaz web para generar audios TTS
- ✅ Selector de 22 emociones disponibles
- ✅ Player de audio integrado
- ✅ Descarga de archivos WAV
- ✅ Estadísticas de generación (tiempo, tamaño, emoción)
- ✅ Grid visual de emociones

### API de Monitoreo
- ✅ REST API completa para métricas y alertas
- ✅ Endpoints de Docker y GPU stats
- ✅ Reporte completo del sistema
- ✅ Integración lista para Prometheus

## Servicios Monitoreados

| Servicio | Puerto | Color |
|----------|--------|-------|
| Gateway | 8800 | Verde |
| Conversation AI | 8801 | Azul |
| TTS Service | 8803 | Naranja |
| Assistant | 8802 | Morado |
| Fish Audio Server | 8080 | Cyan |

## Instalación

```bash
cd services/monitoring-service
pip install -e .
```

## Uso

### ⚡ Arranque Rápido (Recomendado)

**Windows (CMD):**
```cmd
cd services\monitoring-service
start.bat
```

**Windows (PowerShell):**
```powershell
cd services\monitoring-service
.\start.ps1
```

**Linux/Mac:**
```bash
cd services/monitoring-service
./start.sh
```

El script automáticamente:
- ✅ Verifica que estés en el directorio correcto
- ✅ Detecta el entorno virtual
- ✅ Inicia el servidor en puerto 8900
- ✅ Habilita auto-reload (desarrollo)
- ✅ Muestra la URL del dashboard

### Arranque Manual

```bash
# Desde el directorio del servicio
cd services/monitoring-service
python -m src.main

# O usando uvicorn directamente
uvicorn src.main:app --host 127.0.0.1 --port 8900 --reload
```

### Acceder al dashboard

Abre tu navegador en:
```
http://127.0.0.1:8900
```

### Páginas disponibles

- **Dashboard de Monitoreo (NUEVO)**: `http://127.0.0.1:8900/monitoring`
- **Dashboard Principal**: `http://127.0.0.1:8900/`
- **TTS Testing**: `http://127.0.0.1:8900/tts`

## API Endpoints

### Health & Status

#### `GET /health`
Health check del test service

#### `GET /api/services/status`
Obtiene el estado de todos los servicios monitoreados

Respuesta:
```json
{
  "tts": {
    "name": "TTS Service",
    "port": 8803,
    "status": "online",
    "response_time_ms": 12.5,
    "color": "#FF9800"
  },
  ...
}
```

### Monitoring Endpoints (NUEVO v2.0)

#### `GET /api/monitoring/metrics`
Métricas detalladas de todos los servicios (uptime, response times, etc.)

#### `GET /api/monitoring/metrics/{service_id}`
Métricas de un servicio específico

#### `GET /api/monitoring/alerts`
Alertas recientes del sistema
- Query params: `limit` (int), `unresolved_only` (bool)

#### `GET /api/monitoring/system-health`
Resumen de salud general del sistema

#### `GET /api/monitoring/full-report`
Reporte completo con servicios, métricas, Docker y GPU

#### `WS /ws/monitoring`
WebSocket para actualizaciones en tiempo real (broadcast cada 5s)

#### `GET /api/docker/status`
Estado del contenedor Fish Speech Docker

#### `GET /api/docker/stats`
Estadísticas de CPU y memoria del contenedor

#### `GET /api/gpu/stats`
Estadísticas de GPU via nvidia-smi (utilización, VRAM, temperatura)

### TTS Endpoints

#### `GET /api/tts/emotions`
Proxy al endpoint de emociones del servicio TTS

#### `POST /api/tts/synthesize`
Proxy al endpoint de síntesis del servicio TTS

Parámetros:
- `text` (string): Texto a sintetizar
- `emotion` (string): Emoción a usar (default: "neutral")

## Estructura del Proyecto

```
services/test-service/
├── src/
│   ├── main.py              # FastAPI application
│   └── static/
│       ├── index.html       # Dashboard principal
│       └── tts.html         # TTS testing page
├── tests/
├── pyproject.toml
└── README.md
```

## Desarrollo

### Añadir un nuevo servicio al monitoreo

Edita `src/main.py` y añade el servicio al diccionario `SERVICES`:

```python
SERVICES = {
    "mi_servicio": {
        "name": "Mi Servicio",
        "port": 8805,
        "health_url": "http://127.0.0.1:8805/health",
        "start_cmd": None,
        "color": "#E91E63"
    }
}
```

### Añadir una nueva página de testing

1. Crea un archivo HTML en `src/static/`
2. Añade un endpoint en `main.py`:
```python
@app.get("/mi-test")
async def mi_test_page():
    return FileResponse(STATIC_DIR / "mi-test.html")
```
3. Añade un botón en `index.html`

## Tecnologías Utilizadas

- **Backend**: FastAPI, Python 3.10+
- **Frontend**: HTML, CSS, JavaScript vanilla
- **HTTP Client**: httpx (async)
- **Servidor**: Uvicorn

## Notas

- El auto-refresh está habilitado por defecto (cada 5 segundos)
- Los health checks tienen un timeout de 3 segundos
- El síntesis TTS tiene un timeout de 30 segundos
- Los archivos estáticos se sirven desde `/static`
