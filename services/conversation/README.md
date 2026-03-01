# Conversation Service — Casiopy

Servicio FastAPI que orquesta el flujo de conversación de Casiopy: recibe mensajes del usuario,
enriquece el contexto con memoria semántica, llama al LLM (Ollama) y registra la interacción.

## Puerto

`8820` (configurado en `.env`)

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | URL de Ollama |
| `OLLAMA_MODEL` | `gemma3` | Modelo activo (p.ej. `casiopy:week05`) |
| `MEMORY_HTTP` | `http://127.0.0.1:8820` | URL del memory-service |
| `GATEWAY_HTTP` | `http://127.0.0.1:8800` | URL del gateway (no usado actualmente) |

## Iniciar

```bash
cd services/conversation
python -m uvicorn src.server:app --host 0.0.0.0 --port 8820 --reload
```

---

## Arquitectura del flujo de chat

```
POST /chat
    │
    ├─ 1. Crear/recuperar sesión en memory-service
    │       POST /sessions  (si usuario nuevo)
    │
    ├─ 2. Obtener system prompt de Core Memory
    │       GET /core-memory/system-prompt  (caché 5 min)
    │
    ├─ 3. Búsqueda semántica de recuerdos relacionados  ← Fase 3
    │       GET /search?q={texto}&threshold=0.75&limit=3&days=90
    │       (timeout 3s — degradación graceful si falla)
    │
    ├─ 4. Construir mensajes al LLM
    │       system = core_memory_prompt + [RECUERDOS RELACIONADOS]
    │       messages = [system] + historial + [user message]
    │
    ├─ 5. Llamar a Ollama
    │       POST http://ollama/api/chat
    │
    ├─ 6. Clasificar emoción de la respuesta
    │       src/emotion.py  (heurístico basado en palabras clave)
    │
    ├─ 7. Registrar interacción en memory-service
    │       POST /interactions  (session_id, input, output, emociones)
    │       El embedding se genera en background (no bloquea la respuesta)
    │
    └─ 8. Actualizar historial en memoria local
            Máximo 20 turnos por sesión (_MAX_HISTORY_TURNS)
```

---

## Endpoints

### `POST /chat`

Envía un mensaje y recibe la respuesta de Casiopy.

**Body:**
```json
{
  "user_id": "stream_viewer_42",
  "text": "¿Qué juego estás jugando hoy?"
}
```

**Response:**
```json
{
  "response": "Hoy toca Dark Souls 3, como siempre torturándome 🐲",
  "emotion": "playful",
  "session_id": "sess_abc123",
  "turn": 3,
  "memories_used": 2
}
```

| Campo | Descripción |
|-------|-------------|
| `response` | Respuesta generada por el LLM |
| `emotion` | Emoción clasificada de la respuesta |
| `session_id` | ID de sesión en el memory-service |
| `turn` | Número de turno en la sesión actual |
| `memories_used` | Número de recuerdos semánticos inyectados |

### `GET /health`

Estado del servicio y conectividad con Ollama.

### `GET /models`

Lista de modelos disponibles en Ollama.

### `DELETE /session/{user_id}`

Resetea la sesión activa de un usuario (limpia historial en memoria local).

---

## Memoria semántica (Fase 3)

Antes de cada llamada al LLM, el servicio recupera hasta **3 interacciones pasadas**
semánticamente similares al mensaje actual y las añade al system prompt:

```
[RECUERDOS RELACIONADOS CON ESTE TEMA]
- (82% similar) Usuario: "¿Cuál es tu juego favorito?" → Casiopy: "Dark Souls, sin duda."
- (77% similar) Usuario: "¿Juegas RPGs?" → Casiopy: "Los JRPGs son mi género favorito..."
[FIN DE RECUERDOS]
```

**Configuración:**
- Umbral de similitud: 0.75 (coseno)
- Límite: 3 recuerdos por turno
- Ventana temporal: 90 días
- Timeout: 3 segundos (si falla, continúa sin recuerdos)

El embedding de cada interacción se genera automáticamente en background al registrarla
(via `POST /interactions` en el memory-service).

---

## Sesiones y historial

- Las sesiones se crean automáticamente al primer mensaje de cada `user_id`
- El historial (máx. 20 turnos) se mantiene en memoria local (`_active_sessions`)
- El historial persiste en el memory-service vía `POST /interactions`
- Al reiniciar el servicio, las sesiones en memoria se pierden pero las interacciones
  permanecen en PostgreSQL

---

## Módulos

| Archivo | Descripción |
|---------|-------------|
| `server.py` | FastAPI app — endpoints, sesiones, inyección de memoria |
| `llm_ollama.py` | Cliente HTTP para Ollama (`/api/chat`) |
| `emotion.py` | Clasificación de emoción heurística |
| `ollama_manager.py` | Gestión del proceso Ollama (start/stop/health) |
| `tools_registry.py` | Registro de herramientas/tools para el LLM |

---

## Degradación graceful

El servicio funciona aunque el memory-service no esté disponible:
- Sin memory-service → sistema prompt por defecto (`_DEFAULT_SYSTEM_PROMPT`)
- Sin búsqueda semántica → responde sin contexto de recuerdos
- Sin registro de interacciones → conversación no se guarda, pero el usuario recibe respuesta

Los errores se loguean pero no interrumpen el flujo.

---

**Versión**: 1.2.0 (Fase 3: inyección de memoria semántica)
**Última actualización**: 2026-02-28
