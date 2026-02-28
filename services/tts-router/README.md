# tts-router

Enrutador central de síntesis de voz. Actúa como **punto de entrada único** para todos los backends TTS del proyecto: gestiona el ciclo de vida de cada proceso (inicio/parada), monitorea su estado y redirige las peticiones de síntesis al servicio apropiado según el modo seleccionado.

---

## Backends disponibles

| Modo | Servicio | Puerto | RTF (medido) | Sample Rate | Caso de uso recomendado |
|---|---|---|---|---|---|
| `casiopy` ★ DEFAULT | Casiopy FT (MeloTTS fine-tune) | 8815 | ~1.5 | 44100 Hz | Voz principal — toda respuesta en directo |
| `stream_fast` | OpenVoice V2 | 8811 | ~1.44 | 22050 Hz | Alternativa rápida con voz base ES |
| `stream_quality` | CosyVoice3 | 8812 | ~3.76 | 24000 Hz | Respuestas de mayor calidad expresiva |
| `content` | Qwen3-TTS | 8813 | ~7.74 | 12000 Hz | Contenido pregrabado / datasets |
| `content_fish` | Fish Speech | 8814 | ~6.56 | 44100 Hz | Contenido de alta fidelidad sin transcript |

> **RTF (Real-Time Factor):** RTF = tiempo de generación / duración del audio. RTF < 1 es más rápido que tiempo real; RTF > 1 es más lento.

**Resultados del test integrado (GPU RTX 5060 Ti, Blackwell):**

| Modo | Duración audio | Tiempo generación | RTF |
|---|---|---|---|
| `casiopy` | — | — | ~1.5 (estimado, no incluido en test_router.py aún) |
| `stream_fast` | 10.66s | 15.37s | 1.442 |
| `stream_quality` | 8.92s | 33.56s | 3.761 |
| `content` | 10.08s | 78.06s | 7.744 |
| `content_fish` | 8.92s | 58.50s | 6.557 |

---

## Entorno de prueba

| Parámetro | Valor |
|---|---|
| Sistema operativo | Windows 11 Pro (build 26200) |
| GPU | NVIDIA RTX 5060 Ti (Blackwell, sm_120, 12 GB VRAM) |
| Python | 3.12 |
| Puerto | 8810 |
| FastAPI | 0.129.0 |
| httpx | async HTTP client |

---

## Requisitos previos

El router **no tiene venv propio**. Usa el entorno virtual principal del proyecto (`../../.venv/` o `../../venv/`). Las dependencias necesarias son mínimas:

```bash
pip install fastapi uvicorn httpx
```

Antes de usar cualquier backend, cada servicio debe estar correctamente instalado. Consulta el README de cada uno:

- [`../tts-casiopy/README.md`](../tts-casiopy/README.md) — Casiopy FT (puerto 8815) ★ DEFAULT
- [`../tts-openvoice/README.md`](../tts-openvoice/README.md) — OpenVoice V2 (puerto 8811)
- [`../tts-cosyvoice/README.md`](../tts-cosyvoice/README.md) — CosyVoice3 (puerto 8812)
- [`../tts-qwen3/README.md`](../tts-qwen3/README.md) — Qwen3-TTS (puerto 8813)
- [`../tts-fish/README.md`](../tts-fish/README.md) — Fish Speech (puerto 8814)

---

## Estructura del servicio

```
tts-router/
├── server.py               # Enrutador FastAPI (puerto 8810)
├── start.bat               # Script de inicio
├── test_router.py          # Test integrado end-to-end (stream_fast, stream_quality, content, content_fish)
└── outputs/                # Audios WAV generados por los tests
    ├── router_test_stream_fast.wav
    ├── router_test_stream_quality.wav
    ├── router_test_content.wav
    └── router_test_content_fish.wav
```

---

## Arrancar el router

```
start.bat
```

O manualmente:

```bash
python server.py
```

El router arranca en `http://127.0.0.1:8810`.

> Los backends **no se inician automáticamente** al arrancar el router. Deben iniciarse explícitamente con `POST /backends/{mode}/start` o mediante el test integrado.

---

## API — Gestión de procesos

### Iniciar un backend

```http
POST http://127.0.0.1:8810/backends/stream_fast/start
```

**Respuesta:**

```json
{
  "ok": true,
  "pid": 12345,
  "message": "Backend 'OpenVoice V2' iniciando (pid=12345). Sondea GET /backends/stream_fast hasta que model_loaded=true."
}
```

El proceso inicia en segundo plano con su propio entorno virtual. Usa `GET /backends/{mode}` para saber cuándo el modelo terminó de cargar.

---

### Esperar a que el modelo cargue

```http
GET http://127.0.0.1:8810/backends/stream_fast
```

**Respuesta (mientras carga):**

```json
{
  "name": "OpenVoice V2",
  "mode": "stream_fast",
  "url": "http://127.0.0.1:8811",
  "online": true,
  "latency_ms": 4.2,
  "model_loaded": false,
  "loading": false,
  "error": null,
  "device": null,
  "process_running": true,
  "pid": 12345
}
```

**Respuesta (listo para usar):**

```json
{
  "name": "OpenVoice V2",
  "mode": "stream_fast",
  "url": "http://127.0.0.1:8811",
  "online": true,
  "latency_ms": 4.2,
  "model_loaded": true,
  "loading": false,
  "error": null,
  "device": "cuda",
  "process_running": true,
  "pid": 12345
}
```

El backend está listo cuando `model_loaded` es `true`.

---

### Detener un backend

```http
POST http://127.0.0.1:8810/backends/stream_fast/stop
```

---

### Detener todos los backends

```http
POST http://127.0.0.1:8810/backends/stopall
```

---

### Estado de todos los backends

```http
GET http://127.0.0.1:8810/backends
```

Devuelve el estado de los cinco backends en paralelo.

---

### Estado general del router

```http
GET http://127.0.0.1:8810/health
```

```json
{
  "ok": true,
  "version": "2.0.0",
  "backends": ["casiopy", "stream_fast", "stream_quality", "content", "content_fish"],
  "running": ["casiopy"]
}
```

---

## API — Síntesis de audio

### `POST /synthesize` — Devuelve Base64

**Body (JSON):**

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `text` | string | requerido | Texto a sintetizar |
| `voice` | string | `"casiopy"` | Nombre de la voz de referencia |
| `mode` | string | `"casiopy"` | Backend a usar (ver tabla de modos) |
| `speed` | float | `1.0` | Velocidad de habla |
| `emotion` | string | `null` | Emoción (soporte varía por backend) |

**Ejemplo con modo DEFAULT (casiopy):**

```json
{
  "text": "Hola, ¿cómo estás? Espero que todo vaya bien.",
  "mode": "casiopy"
}
```

**Ejemplo con modo alternativo:**

```json
{
  "text": "Hola, ¿cómo estás? Espero que todo vaya bien.",
  "voice": "casiopy",
  "mode": "stream_fast",
  "speed": 1.0
}
```

**Respuesta:**

```json
{
  "ok": true,
  "audio_b64": "<base64 WAV>",
  "sample_rate": 22050,
  "duration_s": 2.4,
  "generation_time_s": 3.5,
  "rtf": 1.44,
  "backend": "openvoice-v2",
  "mode": "stream_fast"
}
```

**Decodificar el audio en Python:**

```python
import base64

audio_bytes = base64.b64decode(response["audio_b64"])
with open("salida.wav", "wb") as f:
    f.write(audio_bytes)
```

---

### `POST /synthesize/wav` — Devuelve WAV directamente

Igual que `/synthesize` pero la respuesta es el archivo WAV con `Content-Type: audio/wav`. Útil para reproducir directamente desde el navegador o con herramientas como `curl`.

```bash
curl -X POST http://127.0.0.1:8810/synthesize/wav \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","voice":"casiopy","mode":"stream_fast"}' \
  --output salida.wav
```

---

### `GET /voices` — Lista voces disponibles

Consulta el primer backend online para obtener las voces disponibles.

```json
{"voices": ["casiopy"]}
```

---

## Test integrado

El archivo `test_router.py` prueba automáticamente los backends de forma secuencial:

```bash
# Probar los 4 backends del test (stream_fast, stream_quality, content, content_fish)
python test_router.py

# Probar solo uno
python test_router.py stream_fast

# Probar backends específicos
python test_router.py stream_fast content_fish
```

> **Nota:** `test_router.py` cubre actualmente los modos `stream_fast`, `stream_quality`, `content` y `content_fish`. Para probar el modo `casiopy` usa la página de pruebas del monitoring service (`/tts-backends`) o un curl directo al router:
>
> ```bash
> curl -X POST http://127.0.0.1:8810/synthesize \
>   -H "Content-Type: application/json" \
>   -d '{"text":"Hola, soy Casiopy.","mode":"casiopy"}' | python -m json.tool
> ```

El test realiza el siguiente ciclo para cada backend:

1. **Inicia** el proceso (`POST /backends/{mode}/start`)
2. **Espera** a que el modelo cargue (sondeo cada 5s con timeout de 5 min)
3. **Sintetiza** el texto de prueba
4. **Guarda** el audio en `outputs/router_test_{mode}.wav`
5. **Detiene** el proceso (`POST /backends/{mode}/stop`)

**Salida esperada:**

```
============================================================
  TTS Router - Prueba integrada
============================================================
Verificando router en http://127.0.0.1:8810
  [OK] Router activo  |  backends: [...]  |  running: []

  Backends a probar: ['stream_fast', 'stream_quality', 'content', 'content_fish']

============================================================
  BACKEND: stream_fast
============================================================
[1/4] Iniciando backend...
  Backend 'OpenVoice V2' iniciando (pid=12345).
[2/4] Esperando que el modelo cargue...
  [OK] Modelo listo
[3/4] Sintetizando audio via router...
  [OK] duration=10.66s  RTF=1.442  backend=openvoice-v2  sr=22050Hz
  [OK] Guardado: outputs/router_test_stream_fast.wav
[4/4] Deteniendo backend...
  [OK] Backend 'stream_fast' detenido

============================================================
  RESUMEN
============================================================
  stream_fast           OK
  stream_quality        OK
  content               OK
  content_fish          OK
============================================================
```

> **Requisito:** El router debe estar corriendo (`start.bat`) antes de ejecutar el test.

---

## Flujo de uso típico

```
1. Iniciar router
   start.bat   (o desde /monitoring → Start tts-router)

2. Iniciar el backend DEFAULT (Casiopy)
   POST /backends/casiopy/start
   — o desde /tts-backends → ⚡ Start Stack

3. Esperar a que cargue (polling)
   GET /backends/casiopy → esperar model_loaded=true

4. Sintetizar texto (modo casiopy es el DEFAULT, no hace falta especificarlo)
   POST /synthesize  { "text": "..." }

5. Al terminar, detener el backend
   POST /backends/casiopy/stop
   — o desde /tts-backends → ⏹ Stop Stack
```

---

## Notas importantes

- **Un backend a la vez.** Con 12 GB de VRAM, solo se puede ejecutar un backend simultáneamente. Si se intenta iniciar un segundo backend mientras hay uno activo, fallará por falta de VRAM.
- **Punto de entrada único.** Todas las peticiones de síntesis del sistema deben pasar por el router (puerto 8810). El monitoring service (`/tts-backends`) ya aplica esta restricción vía proxy.
- **Cierre automático.** Al cerrar el router (`Ctrl+C`), todos los backends iniciados se terminan automáticamente.
- **Timeouts por backend.** Cada backend tiene su timeout de conexión configurado individualmente:
  - `casiopy`: 60s
  - `stream_fast`: 60s
  - `stream_quality`: 120s
  - `content` y `content_fish`: 300s
- **Casiopy comparte venv con tts-openvoice.** El router lanza `tts-casiopy` usando el ejecutable Python de `services/tts-openvoice/venv/`. El resto de backends usan sus propios venvs en `services/tts-*/venv/Scripts/python.exe`.
- **Texto sin caracteres especiales.** El backend `casiopy` (MeloTTS) no acepta emojis ni símbolos no-latinos (p.ej. ★). Filtrar el texto antes de enviar si el origen es dinámico.
