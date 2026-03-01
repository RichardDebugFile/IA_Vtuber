# casiopy-app — Frontend web VTuber Beta

**Puerto:** 8830
**Versión:** 1.0.0
**Estado:** ✅ Producción

Interfaz web de chat para interactuar con Casiopy. Solo conoce la URL del gateway — toda la lógica de conversación, TTS y STT se delega a `gateway:8800`.

---

## Inicio rápido

```bash
cd casiopy-app
# Copiar y configurar variables de entorno (opcionales si usas defaults)
copy .env.example .env

# Instalar dependencias en el venv del proyecto
..\venv\Scripts\pip install -r requirements.txt

# Iniciar
start.bat              # Windows
# o: bash start.sh    # Unix / WSL
```

El servidor arranca en `http://127.0.0.1:8830`.

### Variables de entorno

| Variable      | Default                    | Descripción              |
|---------------|----------------------------|--------------------------|
| `GATEWAY_URL` | `http://127.0.0.1:8800`   | URL HTTP del gateway     |
| `GATEWAY_WS`  | `ws://127.0.0.1:8800`     | URL WebSocket del gateway|

---

## API

### `GET /health`
```json
{"status": "ok", "service": "casiopy-app", "version": "1.0.0"}
```

### `GET /config`
Expone la configuración del gateway al frontend:
```json
{"gateway_url": "http://127.0.0.1:8800", "gateway_ws": "ws://127.0.0.1:8800"}
```

### `GET /` y cualquier ruta
Devuelve `static/index.html` (SPA).

---

## Interfaz

### Vista de carga
Al abrir la app se muestra el estado de los servicios:
- **Memoria API** (opcional): búsqueda semántica de recuerdos
- **Conversación** (requerido): el LLM que da respuestas
- **TTS Blips** (opcional): síntesis de voz fallback
- **TTS Router** (opcional): síntesis de voz principal

Botón **"Iniciar servicios"** → llama a `gateway:8800/services/{id}/start` en orden.
Cuando conversación está online, se habilita **"Ir al chat"**.

### Vista de chat
- **Selector TTS:** `casiopy` (fine-tuned) | `stream_fast` (OpenVoice streaming) | `blips` (siempre disponible)
- **Área de mensajes:** historial de conversación con indicador de emoción
- **Botón 🎤:** graba audio → transcribe vía STT → llena el input
- **Botón ➤ / Enter:** envía mensaje → respuesta + audio (si TTS disponible)
- **Dots de estado:** indicadores en tiempo real de cada servicio (via WebSocket)

### Flujo completo
```
Usuario escribe/habla
  │
  ├─ STT (opcional): /orchestrate/stt → texto transcrito en el input
  │
  └─ Enviar: POST /orchestrate/chat
       │
       ├─ gateway → conversation:8801 → respuesta + emoción
       ├─ gateway → tts-router:8810 o tts-blips:8805 → audio WAV
       └─ casiopy-app: muestra reply + reproduce audio
```

---

## Estructura

```
casiopy-app/
├── server.py          ← FastAPI: /health, /config, SPA fallback
├── requirements.txt   ← fastapi, uvicorn, python-dotenv
├── .env.example       ← variables de entorno
├── start.bat          ← lanzador Windows
├── start.sh           ← lanzador Unix
└── static/
    ├── index.html     ← UI completa (loading + chat), sin dependencias externas
    └── js/
        └── app.js     ← toda la lógica (init, services, chat, audio, STT, WS)
```

---

## Dependencias de servicios

casiopy-app solo necesita el gateway activo. El gateway gestiona el resto:

```
casiopy-app:8830
    └─ gateway:8800 (punto de entrada único)
           ├─ conversation:8801
           ├─ memory-api:8820
           ├─ tts-router:8810
           ├─ tts-blips:8805
           └─ stt:8803
```

---

**Última actualización:** 2026-02-28
**Versión:** 1.0.0 (VTuber Beta)
