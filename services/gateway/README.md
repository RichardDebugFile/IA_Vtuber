# Gateway — Hub central de Casiopy VTuber

**Puerto:** 8800
**Versión:** 2.0.0
**Estado:** ✅ Producción

Punto de entrada único del sistema VTuber. Todos los clientes (casiopy-app, face-service-2D-simple, etc.) se conectan **solo** al gateway. El gateway orquesta internamente la conversación, la síntesis de voz y la gestión de servicios.

---

## Inicio rápido

```bash
cd services/gateway
pip install -e .          # instala fastapi, uvicorn, httpx, python-multipart, pydantic
uvicorn src.main:app --host 127.0.0.1 --port 8800 --reload
```

Variables de entorno opcionales (todos tienen defaults):

| Variable | Default | Descripción |
|---|---|---|
| `CONVERSATION_URL` | `http://127.0.0.1:8801` | Servicio de conversación |
| `TTS_ROUTER_URL` | `http://127.0.0.1:8810` | Enrutador TTS |
| `TTS_BLIPS_URL` | `http://127.0.0.1:8805` | TTS blips (fallback) |
| `STT_URL` | `http://127.0.0.1:8803` | Speech-to-Text |
| `MONITORING_URL` | `http://127.0.0.1:8900` | Monitoring-service (start/stop) |

---

## API

### `GET /health`

Estado del gateway y estadísticas de suscriptores.

```json
{
  "status": "ok",
  "service": "gateway",
  "version": "2.0.0",
  "topics": ["audio", "avatar-action", "emotion", "service-status", "utterance"],
  "subscribers": {"utterance": 2, "emotion": 2, "audio": 1, "service-status": 1, "avatar-action": 0}
}
```

---

### `POST /publish`

Publica un evento manualmente en un tópico. Lo reciben todos los suscriptores WS activos.

```json
// Body
{"topic": "emotion", "data": {"emotion": "happy"}}

// Response
{"ok": true, "topic": "emotion", "delivered": 2}
```

**Tópicos válidos:** `utterance`, `emotion`, `avatar-action`, `audio`, `service-status`

---

### `WS /ws`

Conexión WebSocket pub/sub. Mensajes entrantes admitidos:

```json
// Suscribirse a uno o varios tópicos
{"type": "subscribe",   "topics": ["emotion", "utterance", "service-status"]}

// Cancelar suscripción
{"type": "unsubscribe", "topics": ["emotion"]}

// Keep-alive
{"type": "ping"}
```

Mensajes salientes:

```json
// Confirmación de suscripción
{"type": "subscribed", "topics": ["emotion", "utterance"]}

// Evento publicado (por /orchestrate/* o por otro cliente via /publish)
{"type": "emotion", "data": {"emotion": "excited"}}

// Respuesta ping
{"type": "pong"}
```

---

### `POST /orchestrate/chat`

**Endpoint principal.** Orquesta un turno completo de conversación:

1. Llama a `conversation:8801/chat` → obtiene `reply + emotion + turn`
2. Sintetiza voz con **fallback automático**:
   - `casiopy` → `tts-router:8810 mode=casiopy` (voz fine-tuned, RTF ~1.5)
   - `stream_fast` → `tts-router:8810 mode=stream_fast` (OpenVoice V2, RTF ~0.74)
   - `blips` → `tts-blips:8805` (síntesis aditiva, siempre disponible)
   - Si el modo solicitado falla: intenta `casiopy` → intenta `blips` → sin audio
3. Publica `utterance`, `emotion`, `audio` al bus WS (otros suscriptores, p.ej. face-service-2D-simple, reciben la emoción para cambiar la sprite del avatar)
4. Retorna el resultado completo

```json
// Body
{
  "text": "¿Qué juego estás jugando?",
  "user_id": "viewer_42",
  "tts_mode": "casiopy"
}

// Response
{
  "reply": "Hoy toca Dark Souls 3, como siempre...",
  "emotion": "excited",
  "audio_b64": "<base64 WAV>",
  "turn": 3,
  "tts_backend_used": "casiopy",
  "memories_used": 2
}
```

| Campo | Descripción |
|---|---|
| `reply` | Respuesta del LLM |
| `emotion` | Emoción clasificada por el conversation-service |
| `audio_b64` | Audio WAV en base64. `null` si todo TTS falló |
| `turn` | Número de turno en la sesión del usuario |
| `tts_backend_used` | Backend que generó el audio: `casiopy`, `stream_fast`, `casiopy_fallback`, `blips`, `blips_fallback`, o `null` |
| `memories_used` | Recuerdos semánticos inyectados al contexto |

**Degradación graceful:** Si el TTS falla completamente, responde sin audio (reply + emotion siguen funcionando). Si conversation falla, retorna HTTP 502.

---

### `POST /orchestrate/stt`

Transcribe audio a texto (proxy a `stt:8803/transcribe`).

```
// Body: multipart/form-data
audio: <archivo de audio> (WebM, WAV, OGG, MP3, FLAC…)

// Response
{
  "text": "¿Qué juego estás jugando hoy?",
  "language": "es",
  "duration_s": 2.4
}
```

**Timeout:** 90s (el modelo Whisper puede tardar en audios largos).

---

### `GET /services/status`

Estado de todos los servicios registrados. Proxy a `monitoring:8900/api/services/status`.

```json
{
  "gateway":      {"status": "online",  "port": 8800, ...},
  "conversation": {"status": "online",  "port": 8801, ...},
  "memory-api":   {"status": "offline", "port": 8820, ...}
}
```

### `GET /services/{service_id}/status`

Estado de un único servicio.

### `POST /services/{service_id}/start`

Inicia un servicio vía monitoring-service. Publica eventos `service-status` al bus WS:
- `{"id": "memory-api", "action": "starting"}` al enviar la petición
- `{"id": "memory-api", "action": "started"}` o `"start_failed"` cuando monitoring responde

Timeout: 60s (algunos servicios tardan en iniciar).

### `POST /services/{service_id}/stop`

Para un servicio. Publica `stopping` → `stopped`. Timeout: 15s.

### `POST /services/{service_id}/restart`

Para y reinicia un servicio. Publica `restarting` → `started|restart_failed`.

---

## Flujo de eventos WS

```
casiopy-app                gateway               face-service-2D-simple
    │                         │                          │
    │── POST /orchestrate/chat ──▶                       │
    │                         │── conversation:8801 ──▶  │
    │                         │◀─ {reply, emotion} ──    │
    │                         │── tts-router:8810 ──▶    │
    │                         │◀─ {audio_b64} ─────      │
    │                         │                          │
    │                         │── broadcast(utterance) ──▶
    │                         │── broadcast(emotion)   ──▶ [cambia sprite]
    │                         │── broadcast(audio)     ──▶
    │                         │                          │
    │◀── {reply, emotion, audio_b64, turn} ──────────    │
```

---

## Topics pub/sub

| Topic | Datos | Publicado por |
|---|---|---|
| `utterance` | `{text, user_id, turn}` | `/orchestrate/chat` |
| `emotion` | `{emotion}` | `/orchestrate/chat` |
| `audio` | `{audio_b64, tts_backend}` | `/orchestrate/chat` |
| `avatar-action` | `{action, ...}` (libre) | Cualquier cliente via `/publish` |
| `service-status` | `{id, action, detail?}` | `/services/{id}/start\|stop\|restart` |

---

## Tests

```bash
cd services/gateway
python -m pytest tests/ -v
```

**24 tests** — todos offline (sin servicios externos):
- Unit: `/health`, `/publish`, errores de validación
- Integration: WebSocket subscribe/unsubscribe/ping-pong/recepción de eventos
- Offline: `/services/*` y `/orchestrate/*` retornan 502 cuando los servicios downstream no están levantados

---

## Arquitectura

```
services/gateway/
├── pyproject.toml         ← dependencias: fastapi, uvicorn, httpx, python-multipart, pydantic
├── src/
│   ├── main.py            ← toda la lógica del gateway (endpoints + helpers)
│   └── auth.py            ← reservado (no implementado)
└── tests/
    ├── conftest.py        ← fixtures: client, sample_topics, sample_event_data
    └── test_gateway.py    ← 24 tests unit + integration
```

---

**Última actualización:** 2026-02-28
**Versión:** 2.0.0 (Fase VTuber Beta — orquestación + gestión de servicios)
