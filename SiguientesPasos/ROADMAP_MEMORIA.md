# Roadmap — Sistema de Memoria y Evolución de Casiopy

> **Objetivo:** Transformar a Casiopy de un LLM genérico con voz a una IA que recuerda,
> aprende y evoluciona con el tiempo — como Neuro-sama pero con arquitectura propia.

**Creado:** 27 de febrero de 2026
**Última revisión:** 27 de febrero de 2026
**Estado general:** 🟡 En planificación

---

## Diagnóstico de partida

El sistema está **85% construido pero desconectado**. Todos los servicios existen
pero no hablan entre sí:

```
HOY:
User → conversation/ → Ollama (modelo base genérico, sin personalidad)

OBJETIVO:
User → conversation/ → memory-service/ → Core Memory + LoRA Pers. + LoRA Episódico → Ollama (casiopy:latest)
           ↑ almacena cada turno              ↑ inyecta contexto y recuerdos
```

### Gaps críticos identificados

| # | Gap | Impacto |
|---|-----|---------|
| G1 | `conversation/` no conectado a `memory-service/` | Sin almacenamiento, sin evolución |
| G2 | LoRA de personalidad entrenado pero NO deployado en Ollama | Casiopy responde como LLM genérico |
| G3 | Sin historial multi-turno persistente | Olvida dentro de la misma sesión |
| G4 | Sin entrenamiento episódico automático semanal | Capa 2 (aprendizaje) nunca se activa |
| G5 | Sin búsqueda semántica RAG (pgvector) | No puede recuperar recuerdos específicos |
| G6 | Sin validación anti-lobotomía integrada | Riesgo de deployar un LoRA que olvida la personalidad |

---

## Fase 1 — Conectar lo que ya existe
**Período estimado: 28 feb – 7 mar 2026**
**Estado: 🔴 Pendiente**

Objetivo: Hacer que Casiopy use su personalidad fine-tuneada y guarde cada conversación.

---

### Tarea 1.1 — Deployar LoRA de personalidad en Ollama
**Fecha objetivo: 28 feb 2026**
**Duración estimada: 2-4 horas**
**Responsable: Richard**

El checkpoint `personality_v2_refined_20251230_163256` ya existe y está entrenado.
Solo hay que ejecutar el script de deploy.

**Pasos:**
```bash
cd services/memory-service
# Activar entorno de entrenamiento
scripts/setup/activate_training_env.bat

# Ejecutar deploy (fusiona LoRA + convierte a GGUF + registra en Ollama)
python scripts/deploy_to_ollama.py --version v2
```

**Resultado esperado:**
- Ollama tendrá un modelo `casiopy:v2` disponible
- `ollama list` mostrará el nuevo modelo

**Criterio de éxito:**
```bash
ollama run casiopy:v2 "¿Cómo te llamas y qué sabes hacer?"
# Debe responder con la personalidad de Casiopy, no como LLM genérico
```

**Notas:**
- Si el deploy_to_ollama.py falla, revisar si necesita ajustes de rutas (las rutas
  en el script pueden ser relativas y necesitar ajuste)
- Alternativa manual: usar `ollama create` con un Modelfile que apunte al GGUF generado

---

### Tarea 1.2 — Conectar conversation/ con memory-service/
**Fecha objetivo: 1-3 mar 2026**
**Duración estimada: 1-2 días**
**Archivos a modificar:** `services/conversation/src/server.py`

Actualmente `server.py` usa un system prompt hardcodeado de una línea y no guarda nada.
Hay que añadir 5 llamadas HTTP al memory-service para cerrar el ciclo.

**Flujo objetivo:**
```
/chat recibido
    ↓
1. POST /sessions → crear sesión (memory-service)
    ↓
2. GET /core-memory/system-prompt/generate → obtener system prompt con personalidad
    ↓
3. Llamar a Ollama con system prompt real + historial de sesión
    ↓
4. POST /interactions → almacenar par input/output con calidad automática
    ↓
5. POST /sessions/{id}/end → cerrar sesión
```

**Puntos de atención:**
- El memory-service debe estar corriendo (puerto 8820) y PostgreSQL activo (Docker)
- El quality score se calcula automáticamente en `interaction_manager.py`
- Manejar el caso de que memory-service esté caído (fallback: responder igual sin guardar)

**Criterio de éxito:**
- Después de una conversación, `GET http://localhost:8820/interactions/recent` muestra los turnos
- El system prompt que llega a Ollama contiene la identidad y personalidad de Casiopy

---

### Tarea 1.3 — Historial multi-turno dentro de una sesión
**Fecha objetivo: 3-5 mar 2026**
**Duración estimada: 1 día**
**Archivos a modificar:** `services/conversation/src/server.py`

Actualmente cada `/chat` es un request independiente — Casiopy olvida lo que dijo hace
2 mensajes. Hay que mantener el hilo de conversación mientras la sesión está activa.

**Diseño:**
- Usar un dict en memoria `active_sessions: dict[session_id, list[messages]]`
- Cada turno: append del user message + assistant reply
- Mantener ventana de los últimos 20 turnos (evitar context overflow)
- Limpiar sesión cuando se llame a finalizar o tras N minutos de inactividad

**Criterio de éxito:**
```
User: "Me llamo Richard"
Casiopy: "Ah, hola Richard..."
User: "¿Cómo me llamo?"
Casiopy: "Te llamas Richard, lo dijiste hace un momento."  ← esto debe funcionar
```

---

### Tarea 1.4 — Actualizar OLLAMA_MODEL en conversation/
**Fecha objetivo: 5 mar 2026**
**Duración estimada: 15 minutos**
**Archivos a modificar:** `services/conversation/.env`

Una vez el deploy de 1.1 esté listo, cambiar el modelo:
```bash
# services/conversation/.env
OLLAMA_MODEL=casiopy:v2   # antes era: gemma3
```

**Criterio de éxito:** Conversación entera con Casiopy usando su personalidad real.

---

### Hito 1 — Verificación completa de Fase 1
**Fecha objetivo: 7 mar 2026**

Prueba de integración completa:
- [ ] `ollama list` muestra `casiopy:v2`
- [ ] Conversación de 10 turnos — Casiopy mantiene contexto
- [ ] `GET /interactions/recent` muestra los 10 turnos guardados con embeddings
- [ ] System prompt de Ollama contiene Core Memory (verificar con logs)
- [ ] Casiopy responde con su personalidad (sarcasmo, referencias a su historia)

---

## Fase 2 — El bucle de aprendizaje automático
**Período estimado: 8 mar – 22 mar 2026**
**Estado: 🔴 Pendiente**

Objetivo: Que Casiopy aprenda automáticamente de las conversaciones cada semana.

---

### Tarea 2.1 — Quality scoring y panel de feedback
**Fecha objetivo: 8-10 mar 2026**
**Duración estimada: 2 días**

El `interaction_manager.py` ya calcula un quality score automático, pero hay que
añadir feedback manual del creador (tú) para supervisar qué entra al entrenamiento.

**Dónde añadirlo:**
- Panel en el monitoring dashboard (puerto 8900) — nueva página `memory.html`
- Listado de interacciones recientes con botones: ✅ Buena respuesta | ❌ Mala | ✏️ Corrección
- La corrección permite escribir cómo debería haber respondido Casiopy

**Endpoints del memory-service ya disponibles:**
- `POST /feedback` — añade retroalimentación
- `PUT /interactions/{id}/quality` — ajusta el score manualmente

---

### Tarea 2.2 — Pipeline de exportación automático
**Fecha objetivo: 10-12 mar 2026**
**Duración estimada: 2 días**
**Archivos a modificar:** `services/memory-service/src/main.py`

Añadir un scheduler (APScheduler) que ejecute el pipeline de exportación cada domingo.

**Flujo automático semanal:**
```
Domingo 23:00
    ↓
1. export_training_data.py — exporta interacciones quality >= 0.6 de los últimos 7 días
    ↓
2. validate_dataset.py — verifica que el dataset es válido y tiene suficientes ejemplos (mín. 50)
    ↓
3. Si OK: train_episodic_lora.py — entrena LoRA Capa 2 (15-30 min, ~6GB VRAM)
    ↓
4. test_personality.py — validación anti-lobotomía (¿sigue siendo Casiopy?)
    ↓
5. Si OK: deploy_to_ollama.py --week N — fusiona Capa 1 + Capa 2 → Ollama casiopy:weekN
    ↓
6. Si falla: revertir a semana anterior + notificar en logs
```

**Criterio de éxito:**
- Después de la primera semana de uso, aparece `casiopy:week1` en Ollama
- Las respuestas reflejan temas de los que se habló esa semana

---

### Tarea 2.3 — Notificaciones de entrenamiento en monitoring
**Fecha objetivo: 12-14 mar 2026**
**Duración estimada: 1 día**

Mostrar en el monitoring dashboard:
- Estado del último entrenamiento episódico (fecha, loss, éxito/fallo)
- Próximo entrenamiento programado
- Número de interacciones acumuladas esta semana (con indicador de si son suficientes)
- Historial de versiones de LoRA deployadas

---

### Hito 2 — Primera semana de aprendizaje real
**Fecha objetivo: 22 mar 2026**

- [ ] Primera semana de conversaciones acumuladas en PostgreSQL
- [ ] Pipeline automático ejecutó exitosamente el domingo
- [ ] `casiopy:week1` disponible en Ollama
- [ ] Respuestas de week1 reflejan los temas de esa semana
- [ ] Panel de feedback operativo con al menos 20 interacciones evaluadas

---

## Fase 3 — Memoria episódica real (largo plazo)
**Período estimado: 23 mar – 15 abr 2026**
**Estado: 🔴 Pendiente**

Objetivo: Que Casiopy pueda recuperar recuerdos específicos de conversaciones pasadas
en tiempo real — "la semana pasada cuando hablamos de Oshi no Ko..."

---

### Tarea 3.1 — Búsqueda semántica con pgvector
**Fecha objetivo: 23-27 mar 2026**
**Duración estimada: 3-4 días**

La infraestructura de pgvector ya está en la BD (`input_embedding` y `output_embedding`
son columnas vector de 384 dims). Hay que usarla.

**Flujo de recuperación de memoria:**
```python
# En conversation/src/server.py, antes de llamar a Ollama:

# 1. Generar embedding del mensaje del usuario
user_embedding = embed(user_text)  # llamada a memory-service/embed

# 2. Buscar interacciones pasadas similares
memories = GET /memory-service/search?embedding=...&threshold=0.75&limit=3

# 3. Inyectar como contexto adicional al system prompt
context = format_memories(memories)
system_prompt = base_system_prompt + "\n\n[RECUERDOS RELEVANTES]\n" + context
```

**Criterio de éxito:**
```
User: "¿Qué piensas de Oshi no Ko?"
Casiopy: "Oye, creo que ya hablamos de esto... [referencia a conversación anterior]"
```

---

### Tarea 3.2 — Añadir endpoint de búsqueda semántica al memory-service
**Fecha objetivo: 23-25 mar 2026**
**Duración estimada: 1-2 días**
**Archivos a modificar:** `services/memory-service/src/main.py`

```python
@app.get("/search")
async def semantic_search(query: str, threshold: float = 0.75, limit: int = 5):
    embedding = embedding_service.encode(query)
    results = await db.fetch("""
        SELECT input_text, output_text, created_at,
               1 - (input_embedding <-> $1::vector) AS similarity
        FROM interactions
        WHERE 1 - (input_embedding <-> $1::vector) > $2
        ORDER BY similarity DESC
        LIMIT $3
    """, embedding, threshold, limit)
    return results
```

---

### Tarea 3.3 — Personalidad drifting controlado
**Fecha objetivo: 1-10 abr 2026**
**Duración estimada: 1 semana**

Implementar un sistema que analice qué rasgos de personalidad refuerza la audiencia:
- Qué emociones genera más interacciones positivas
- Qué temas generan más engagement
- Ajustar los pesos de muestreo en el dataset semanal para amplificar esos rasgos

**Objetivo:** Casiopy "evoluciona" en la dirección que su audiencia moldea, sin perder
su identidad core (Capa 0 sigue siendo inmutable).

---

### Hito 3 — Memoria episódica operativa
**Fecha objetivo: 15 abr 2026**

- [ ] Búsqueda semántica funcional en < 200ms
- [ ] Casiopy menciona conversaciones pasadas de forma natural
- [ ] Al menos 4 semanas de LoRAs episódicos acumulados
- [ ] Métricas de drift de personalidad visibles en el dashboard
- [ ] Casiopy es notablemente diferente a un LLM genérico en conversación libre

---

## Resumen visual del calendario

```
Feb 2026
└── 28 feb ──────── [1.1] Deploy LoRA personalidad → Ollama casiopy:v2

Mar 2026
├── 01-03 mar ───── [1.2] Conectar conversation ↔ memory-service
├── 03-05 mar ───── [1.3] Historial multi-turno
├── 05 mar ─────── [1.4] Cambiar OLLAMA_MODEL a casiopy:v2
├── 07 mar ─────── ✅ HITO 1: Casiopy tiene memoria básica
│
├── 08-10 mar ───── [2.1] Panel de feedback en monitoring
├── 10-12 mar ───── [2.2] Pipeline de exportación + entrenamiento automático
├── 12-14 mar ───── [2.3] Notificaciones de entrenamiento en dashboard
├── 22 mar ─────── ✅ HITO 2: Primera semana de aprendizaje real

Abr 2026
├── 23-27 mar ───── [3.1] Búsqueda semántica pgvector
├── 23-25 mar ───── [3.2] Endpoint /search en memory-service
├── 01-10 abr ───── [3.3] Personalidad drifting
└── 15 abr ─────── ✅ HITO 3: Memoria episódica operativa
```

---

## Dependencias entre tareas

```
1.1 (Deploy LoRA)
 └→ 1.4 (Cambiar OLLAMA_MODEL)

1.2 (Conectar conversation ↔ memory)
 └→ 1.3 (Historial multi-turno)
     └→ 2.1 (Panel feedback)
         └→ 2.2 (Pipeline automático)
             └→ 2.3 (Notificaciones dashboard)
                 └→ 3.1 (Búsqueda semántica)
                     └→ 3.2 (Endpoint /search)
                         └→ 3.3 (Personality drifting)
```

**Bloqueo crítico:** La Tarea 1.2 es la más importante. Sin ella,
nada de Fase 2 ni Fase 3 es posible.

---

## Decisiones pendientes

| # | Decisión | Opciones | Impacto |
|---|----------|---------|---------|
| D1 | ¿Tamaño de ventana de historial por sesión? | 10 / 20 / 50 turnos | VRAM de Ollama |
| D2 | ¿Umbral mínimo de ejemplos para entrenar Capa 2? | 30 / 50 / 100 | Calidad del LoRA episódico |
| D3 | ¿Frecuencia del entrenamiento episódico? | Diario / Semanal / Mensual | VRAM y tiempo de cómputo |
| D4 | ¿El drift de personalidad es automático o supervisado? | Auto / Manual / Híbrido | Riesgo de desviación indeseada |
| D5 | ¿ChromaDB además de pgvector, o solo pgvector? | Ambos / Solo pgvector | Complejidad vs. capacidad |

---

## Notas técnicas relevantes

- **VRAM disponible:** RTX 5060 Ti (16 GB) — suficiente para LoRA Capa 1 (~8GB) y Capa 2 (~6GB)
- **Base model:** `NousResearch/Hermes-3-Llama-3.1-8B` con 4-bit quantization
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384 dims, ya en memory-service)
- **PostgreSQL:** Docker, puerto 8821, con extensión pgvector ya configurada
- **LoRA actual listo:** `personality_v2_refined_20251230_163256` — Loss: 0.033, ~9.2 epochs efectivos

---

*Documento generado el 27 de febrero de 2026. Actualizar fechas y estados conforme avance el proyecto.*
