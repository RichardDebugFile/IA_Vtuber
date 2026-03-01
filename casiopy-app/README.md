# casiopy-app — Frontend web VTuber Beta

**Puerto:** 8830
**Versión:** 1.1.0
**Estado:** ✅ Producción

Interfaz web de chat para interactuar con Casiopy. Gestiona el arranque de servicios, el chat, el audio TTS/STT y el monitoreo en tiempo real (VRAM, logs de auditoría).

---

## Inicio rápido

```bash
# Desde la raíz del proyecto:
casiopy-app\start.bat        # Windows  — lanza monitoring-service (8900) + casiopy-app (8830)
# o: bash casiopy-app/start.sh   # Unix / WSL
```

El `start.bat` realiza en orden:
1. Comprueba si `monitoring-service` ya está activo en el puerto 8900; si no, lo arranca.
2. Arranca `casiopy-app` en primer plano (8830) mostrando los logs en la ventana.
3. Abre el navegador automáticamente en `http://127.0.0.1:8830` tras 4 segundos.

### Variables de entorno (`.env` en `casiopy-app/`)

| Variable         | Default                   | Descripción                         |
|------------------|---------------------------|-------------------------------------|
| `GATEWAY_URL`    | `http://127.0.0.1:8800`  | URL HTTP del gateway                |
| `GATEWAY_WS`     | `ws://127.0.0.1:8800`    | URL WebSocket del gateway           |
| `MONITORING_URL` | `http://127.0.0.1:8900`  | URL interna del monitoring-service  |

---

## API

### `GET /health`
```json
{"status": "ok", "service": "casiopy-app", "version": "1.0.0"}
```

### `GET /config`
Expone las URLs de backend al frontend JavaScript:
```json
{
  "gateway_url":    "http://127.0.0.1:8800",
  "gateway_ws":     "ws://127.0.0.1:8800",
  "monitoring_url": "http://127.0.0.1:8900"
}
```

### `GET|POST /mon/{path}`
**Proxy transparente** hacia `monitoring-service` (8900). Elimina la necesidad de CORS en el browser — el frontend llama a rutas relativas `/mon/api/...` sobre el mismo origen (8830).

Ejemplos de rutas proxied:
- `GET /mon/api/services/status` → estado de todos los servicios
- `POST /mon/api/services/{id}/start` → arrancar un servicio
- `POST /mon/api/services/{id}/stop` → detener un servicio
- `GET /mon/api/vram/status` → uso de VRAM GPU
- `POST /mon/api/vram/guard` → configurar guardia VRAM
- `GET /mon/api/logs/recent?limit=N` → últimos N eventos de auditoría

### `GET /` y cualquier ruta no definida
Devuelve `static/index.html` (SPA fallback).

---

## Interfaz

### Vista de carga
Muestra el estado de los servicios en tiempo real y permite arrancarlos:

| Servicio            | Puerto | Tipo      |
|---------------------|--------|-----------|
| Gateway             | 8800   | requerido |
| Memoria DB (PostgreSQL) | 5432 | opcional |
| Memoria API         | 8820   | opcional  |
| Conversación        | 8801   | requerido |
| TTS Blips           | 8805   | opcional  |
| TTS Router          | 8810   | opcional  |
| TTS Casiopy (voz)   | 8815   | opcional  |
| STT — Voz a texto   | 8803   | opcional  |

Cada fila muestra: indicador de color · nombre · puerto · tiempo de respuesta (ms) · estado.

**Botón "Iniciar servicios"** → arranca la secuencia en orden, llamando a `/mon/api/services/{id}/start` para cada servicio offline. El endpoint espera hasta 5 s a que el proceso escuche en su puerto antes de reportar `online` o `offline`.

**Barra de progreso** → porcentaje de servicios online.

**Panel de auditoría** (fijo en el fondo) → muestra los últimos eventos del monitoring-service en tiempo real (refresh 5 s). Filtros automáticos para reducir el ruido de health checks. Expandible/colapsable con clic.

### Vista de chat
- **Selector TTS:** `casiopy` (fine-tuned) | `blips` (siempre disponible)
- **Área de mensajes:** historial con indicador de emoción por respuesta
- **Botón 🎤:** graba audio → transcribe vía STT → llena el input
- **Botón ➤ / Enter:** envía mensaje → respuesta de Casiopy + audio WAV
- **Mini-dots de estado:** indicadores en tiempo real de gateway, conversación, memoria, TTS Casiopy y STT (vía WebSocket del gateway)
- **Badge VRAM:** muestra uso de GPU en tiempo real. Color verde/amarillo/rojo según umbrales. Clic para refrescar.
- **Botón 📋:** abre/cierra el panel de auditoría en esquina inferior derecha

### Flujo completo

```
Usuario escribe / habla
  │
  ├─ [opcional] 🎤 STT: POST /orchestrate/stt
  │       → gateway → stt:8803 → texto transcrito
  │
  └─ ➤ Enviar: POST /orchestrate/chat
         │
         ├─ gateway → conversation:8801 → respuesta + emoción
         └─ gateway → tts-router:8810 (o tts-blips:8805) → audio WAV
                casiopy-app: muestra reply + reproduce audio
```

---

## Monitoreo en tiempo real

### VRAM Guard
Polling cada 30 s a `/mon/api/vram/status`. Muestra uso de VRAM, temperatura y utilización GPU en el tooltip del badge. Si el monitoring-service detecta VRAM ≥ 90%, para automáticamente los servicios TTS/STT y notifica con un toast.

Niveles del badge:
- **Verde** (`ok`) — VRAM < 80 %
- **Amarillo** (`warn`) — VRAM 80–89 %
- **Rojo parpadeante** (`critical`) — VRAM ≥ 90 %

### Panel de auditoría
Consume `/mon/api/logs/recent`. Muestra eventos `SERVICE_CONTROL` (arranques/paradas) y `TTS_SYNTHESIS`. Los events de tipo `API_REQUEST` para `/health` y `/api/services/status` se filtran para no saturar la vista.

---

## Estructura

```
casiopy-app/
├── server.py          ← FastAPI: /health, /config, proxy /mon/**, SPA fallback
├── requirements.txt   ← fastapi, uvicorn, httpx, python-dotenv
├── .env.example       ← variables de entorno
├── start.bat          ← lanzador Windows (arranca monitoring-service + app)
├── start.sh           ← lanzador Unix
├── tests/
│   └── test_server.py ← 19 tests (health, config, proxy routes, SPA fallback)
└── static/
    ├── index.html     ← UI completa (loading + chat), sin dependencias externas
    └── js/
        └── app.js     ← lógica completa: init, services, chat, audio, STT, WS,
                          VRAM guard, logs/auditoría
```

---

## Dependencias de servicios

```
Browser
  └─ casiopy-app:8830
       ├─ /mon/**  →  monitoring-service:8900  (proxy, gestión de servicios, logs, VRAM)
       └─ gateway:8800  (chat, STT, WebSocket de eventos)
              ├─ conversation:8801
              ├─ memory-api:8820
              │     └─ memory-postgres:5432 (Docker)
              ├─ tts-router:8810
              │     ├─ tts-casiopy:8815
              │     ├─ tts-openvoice:8811
              │     └─ ...
              ├─ tts-blips:8805
              └─ stt:8803
```

---

**Última actualización:** 2026-03-01
**Versión:** 1.1.0 (VTuber Beta)
