# tts-casiopy

Servicio de síntesis de voz con la voz **fine-tuneada de Casiopy**. Es el backend TTS principal del proyecto y el modo `casiopy` del [tts-router](../tts-router/README.md).

No usa ToneColorConverter: el modelo fine-tuneado ya habla directamente como Casiopy, lo que reduce la latencia y simplifica la cadena de audio.

---

## Resumen

| Parámetro | Valor |
|---|---|
| Puerto | **8815** |
| Modo en tts-router | `casiopy` (DEFAULT) |
| Arquitectura | MeloTTS (VITS) fine-tuneado |
| Checkpoint activo | `model/G_24500.pth` |
| Sample rate | 44 100 Hz |
| Dispositivo | CUDA (fallback CPU) |
| Venv | Compartido con `tts-openvoice` |
| RTF medido (RTX 5060 Ti) | ~1.5 |

---

## Descripción técnica

### Modelo base

[MeloTTS](https://github.com/myshell-ai/MeloTTS) es un TTS basado en VITS con soporte multilingüe y multi-speaker. El servicio carga un checkpoint fine-tuneado a partir del speaker `ES` del modelo base, añadiendo el speaker `casiopy` (speaker ID = 1).

```
Speakers registrados en config.json:
  "ES":      0   ← voz base española (no usada en producción)
  "casiopy": 1   ← voz fine-tuneada (speaker ID activo)
```

### Sin ToneColorConverter

La arquitectura de [tts-openvoice](../tts-openvoice/) usa MeloTTS como TTS base y aplica después un ToneColorConverter (TCC) para clonar el timbre de la voz de referencia. Este servicio **omite ese paso** porque el fine-tune ya captura el timbre directamente, lo que:

- Reduce el RTF (~1.5 vs ~0.2 en openvoice sin TCC medido en servidor)
- Elimina la necesidad de un audio de referencia en runtime
- Produce una voz más consistente entre frases

### Pipeline de audio

```
Texto
  │
  ▼
MeloTTS.tts_to_file()          ← VITS, noise_scale, speed
  │  temp WAV @ 44100 Hz
  ▼
Pitch shift (PSOLA / librosa)  ← pitch_shift (semitones)
  │
  ▼
High-shelf boost (scipy)       ← brightness (dB, freq ≥ 3 kHz)
  │
  ▼
PCM_16 WAV en memoria          ← devuelto como audio_b64
```

### Escaneo automático de checkpoint

Al iniciar, el servicio escanea `model/` y carga el archivo `G_*.pth` **más reciente** (por nombre). Para actualizar el modelo basta con copiar el nuevo checkpoint y reiniciar el servicio.

---

## Parámetros óptimos

Hallados experimentalmente con el Pitch Tester sobre `G_24500.pth` en RTX 5060 Ti:

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `pitch_shift` | `+1.0` st | El modelo fine-tuneado tiende a ser ligeramente grave |
| `brightness` | `+2.5` dB | Boost de presencia en altas frecuencias (≥ 3 kHz) |
| `noise_scale` | `0.65` | Variación expresiva (MeloTTS default = 0.667) |
| `speed` | `1.0` | Velocidad de habla |

Estos valores son los defaults de la API y no es necesario enviarlos explícitamente salvo que se quiera sobreescribirlos.

---

## Estructura del servicio

```
tts-casiopy/
├── server.py          # FastAPI (puerto 8815)
├── start.bat          # Inicio manual
└── model/
    ├── G_24500.pth    # Checkpoint fine-tuneado (activo)
    └── config.json    # Configuración del modelo
```

---

## Entorno de ejecución

El servicio **no tiene venv propio**. Usa el entorno virtual de `tts-openvoice`, que ya incluye todas las dependencias necesarias:

```
services/tts-openvoice/venv/
```

**Dependencias principales:**
- `torch` + CUDA
- `melo` (MeloTTS, versión parchada del proyecto)
- `soundfile`
- `parselmouth` (pitch shift PSOLA, preferido)
- `librosa` (pitch shift fallback)
- `scipy` (filtro de brillo)
- `fastapi`, `uvicorn`

---

## Inicio

### Con el monitoring service

Desde `http://127.0.0.1:8900/tts-backends` → botón **▶ Iniciar** en la tarjeta de Casiopy FT.

O desde el monitoring principal (`/monitoring`) → botón Start en el servicio `tts-casiopy`.

### Manual

```bat
start.bat
```

```bash
# O directamente con el Python del venv de tts-openvoice
..\tts-openvoice\venv\Scripts\python.exe server.py
```

El servicio arranca en `http://127.0.0.1:8815`. El modelo se carga en segundo plano; consulta `GET /health` para saber cuándo está listo.

---

## API

### `GET /health`

```json
{
  "ok": true,
  "service": "tts-casiopy",
  "model_loaded": true,
  "loading": false,
  "error": null,
  "checkpoint": "G_24500.pth",
  "device": "cuda"
}
```

`model_loaded` es `false` mientras el checkpoint se está cargando en VRAM. El servicio responde con HTTP 200 en ambos casos; es el campo `model_loaded` el que indica si está listo para sintetizar.

---

### `GET /voices`

```json
{
  "voices": [
    {
      "id":      "casiopy",
      "name":    "Casiopy",
      "lang":    "ES",
      "model":   "G_24500.pth",
      "backend": "melo-ft"
    }
  ]
}
```

---

### `POST /synthesize`

**Body (JSON):**

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `text` | string | requerido | Texto a sintetizar |
| `voice` | string | `"casiopy"` | Solo hay una voz; campo informativo |
| `speed` | float | `1.0` | Velocidad de habla |
| `pitch_shift` | float | `1.0` | Desplazamiento de tono en semitonos |
| `brightness` | float | `2.5` | Boost de altas frecuencias en dB |
| `noise_scale` | float | `0.65` | Variabilidad expresiva del modelo VITS |
| `emotion` | string | `null` | Reservado — sin efecto en esta versión |

**Ejemplo mínimo:**

```json
{
  "text": "Hola, soy Casiopy. ¿En qué te puedo ayudar?"
}
```

**Ejemplo con parámetros completos:**

```json
{
  "text": "Hola, soy Casiopy. ¿En qué te puedo ayudar?",
  "speed": 1.05,
  "pitch_shift": 1.0,
  "brightness": 2.5,
  "noise_scale": 0.65
}
```

**Respuesta:**

```json
{
  "ok": true,
  "audio_b64": "<base64 WAV>",
  "sample_rate": 44100,
  "duration_s": 2.1,
  "generation_time_s": 3.2,
  "rtf": 1.52,
  "backend": "casiopy-ft",
  "checkpoint": "G_24500.pth",
  "pitch_algo": "psola"
}
```

| Campo | Descripción |
|---|---|
| `audio_b64` | Audio WAV codificado en Base64 |
| `sample_rate` | 44 100 Hz |
| `rtf` | Real-Time Factor (tiempo generación / duración audio) |
| `backend` | Siempre `"casiopy-ft"` |
| `checkpoint` | Nombre del archivo `.pth` cargado |
| `pitch_algo` | `"psola"` (parselmouth) o `"librosa"` (fallback) |

**Decodificar el audio en Python:**

```python
import base64, requests

r = requests.post("http://127.0.0.1:8815/synthesize",
                  json={"text": "Hola, soy Casiopy."})
audio = base64.b64decode(r.json()["audio_b64"])
open("casiopy_out.wav", "wb").write(audio)
```

**Errores posibles:**

| HTTP | Causa |
|---|---|
| `400` | Texto vacío |
| `503` | Modelo cargando (`loading=true`) o no disponible (`model_loaded=false`) |

---

## Uso a través del tts-router

En producción, **todas las peticiones de síntesis deben pasar por el tts-router** (puerto 8810). El modo `casiopy` es el DEFAULT del router.

```json
POST http://127.0.0.1:8810/synthesize
{
  "text": "Hola, soy Casiopy.",
  "mode": "casiopy"
}
```

Si no se especifica `mode`, el router usa `casiopy` por defecto.

Los parámetros específicos del backend (`pitch_shift`, `brightness`, `noise_scale`) **no están expuestos en el router** — éste pasa solo `text`, `voice`, `speed` y `emotion`. Los valores óptimos son los defaults del servidor, por lo que no es necesario enviarlos.

---

## Notas

- **VRAM:** ~3 GB con CUDA. No es compatible con otros backends pesados simultáneamente.
- **Temperatura de carga:** El primer health check tras el inicio puede tardar 15–30 segundos en RTX 5060 Ti.
- **Texto problemático:** Caracteres no-latinos (emojis, símbolos como ★) pueden causar error 500 en MeloTTS. Filtrar el texto antes de enviar si el origen es dinámico.
- **Checkpoint más reciente:** El servicio siempre carga el `G_*.pth` con el nombre lexicográficamente mayor. Copiar un checkpoint nuevo y reiniciar es suficiente para actualizar el modelo.
