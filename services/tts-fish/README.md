# tts-fish

Servicio wrapper de **Fish Speech** (modelo `openaudio-s1-mini`) que expone una API HTTP para síntesis de voz con clonación zero-shot. Fish Speech es un modelo basado en LLM que produce audio a 44100 Hz, la mayor calidad entre los servicios disponibles.

---

## Créditos

| Componente | Repositorio | Organización | Licencia |
|---|---|---|---|
| **Fish Speech** | [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) | Fish Audio | Apache 2.0 (código) |
| **openaudio-s1-mini** | [fishaudio/openaudio-s1-mini (HuggingFace)](https://huggingface.co/fishaudio/openaudio-s1-mini) | Fish Audio | **CC-BY-NC-SA-4.0** (modelos) |

> **Atención — Licencia de modelos:** Los pesos del modelo están bajo **CC-BY-NC-SA-4.0 (No Comercial)**. Esto significa que **no está permitido el uso comercial** sin autorización expresa de Fish Audio. Para uso comercial, consulta [fish.audio](https://fish.audio).

---

## Entorno de prueba

| Parámetro | Valor |
|---|---|
| Sistema operativo | Windows 11 Pro (build 26200) |
| GPU | NVIDIA RTX 5060 Ti (Blackwell, sm_120, 12 GB VRAM) |
| CUDA | 12.8 |
| Python | 3.12 |
| PyTorch | 2.7.0+cu128 |
| fish-speech | 0.1.0 (instalado editable desde `repo/`) |
| protobuf | **3.19.6** (versión fija — incompatible con otros servicios) |
| RTF medido | ~6.56 (texto ~160 chars → 8.9s de audio) |
| VRAM utilizada | ~4–6 GB |
| Sample rate salida | **44100 Hz** (mayor calidad entre todos los servicios) |

> **RTF (Real-Time Factor):** RTF = tiempo de generación / duración del audio. RTF < 1 es más rápido que tiempo real; RTF > 1 es más lento.

---

## Cómo funciona

Fish Speech es un modelo **LLM-based** de dos etapas:

1. **LLM (Llama-based):** Convierte el texto de entrada en tokens de audio (códigos VQ).
2. **VQ-GAN Codec:** Decodifica los tokens de audio en waveform PCM a 44100 Hz.

La clonación de voz se realiza en modo **zero-shot**: solo se necesita un archivo `.wav` de referencia. El modelo extrae el estilo de la voz directamente del audio sin ningún entrenamiento adicional.

---

## Estructura del servicio

```
tts-fish/
├── server.py               # Servicio FastAPI (puerto 8814)
├── start.bat               # Script de inicio
├── setup_venv.bat          # Configuración del entorno virtual
├── requirements.txt        # Dependencias Python
├── outputs/                # Audios generados por los tests
├── venv/                   # Entorno virtual local (generado)
└── repo/                   # Repositorio fish-speech (clonado localmente)
    ├── fish_speech/        # Módulo Python principal
    │   └── utils/
    │       └── schema.py   # ServeTTSRequest, ServeReferenceAudio
    ├── tools/
    │   └── server/
    │       └── model_manager.py   # ModelManager (carga LLM + codec)
    ├── checkpoints/
    │   └── openaudio-s1-mini/    # Pesos del modelo
    │       ├── model.pth          # LLM (Llama-based)
    │       ├── codec.pth          # VQ-GAN decoder
    │       ├── config.json
    │       ├── special_tokens.json
    │       └── tokenizer.tiktoken
    └── pyproject.toml
```

---

## Instalación paso a paso

### Requisitos previos

- Python 3.12 ([python.org](https://www.python.org/downloads/))
- CUDA 12.8
- `protobuf==3.19.6` es **incompatible** con `protobuf>=4.x` que usan otros servicios — se requiere venv separado

---

### Paso 1 — Clonar Fish Speech

```bash
git clone https://github.com/fishaudio/fish-speech.git repo
```

Esto crea la carpeta `repo/` con todo el código fuente de Fish Speech.

---

### Paso 2 — Descargar el modelo openaudio-s1-mini

Desde Hugging Face:

```
https://huggingface.co/fishaudio/openaudio-s1-mini
```

Con `huggingface-cli`:

```bash
pip install huggingface-hub
huggingface-cli download fishaudio/openaudio-s1-mini --local-dir repo\checkpoints\openaudio-s1-mini
```

La estructura esperada tras la descarga:

```
repo/checkpoints/openaudio-s1-mini/
├── model.pth
├── codec.pth
├── config.json
├── special_tokens.json
└── tokenizer.tiktoken
```

---

### Paso 3 — Configurar el entorno virtual

```
setup_venv.bat
```

El script copia el venv desde `D:\ExperimentosPython\TTS-Google\fish-speech\venv` (si existe) y actualiza las rutas del paquete editable. Si no existe, instala desde `requirements.txt`.

**Instalación manual alternativa:**

```bash
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
venv\Scripts\pip install -e repo --no-deps
```

> El flag `--no-deps` en `pip install -e repo` es **obligatorio** para evitar que fish-speech sobreescriba versiones de dependencias ya instaladas.

---

### Paso 4 — Preparar el audio de referencia

Fish Speech no requiere transcripción. Solo necesita un archivo `.wav`:

```
services/tts/reference/
└── casiopy/
    └── CasiopyVoz-15s.wav   # Audio de referencia (preferiblemente >10 segundos)
```

El servicio selecciona automáticamente el `.wav` de **mayor tamaño** de la carpeta. Si hay varios archivos, se usa el más grande asumiendo que tiene más duración.

---

## Arrancar el servicio

```
start.bat
```

O manualmente:

```bash
venv\Scripts\python server.py
```

El servidor arranca en `http://127.0.0.1:8814`. La carga del modelo (LLM + codec) tarda ~20–40 segundos.

Verifica el estado:

```
GET http://127.0.0.1:8814/health
```

---

## API

### `GET /health`

Siempre responde 200 (incluso durante la carga del modelo).

```json
{
  "ok": true,
  "model_loaded": true,
  "loading": false,
  "error": null,
  "backend": "fish-speech-local",
  "device": "cuda"
}
```

---

### `GET /voices`

```json
{"voices": ["casiopy"]}
```

---

### `POST /synthesize`

Además de los campos estándar, este servicio acepta parámetros de inferencia del LLM.

**Body (JSON):**

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `text` | string | requerido | Texto a sintetizar |
| `voice` | string | `"casiopy"` | Nombre de la voz de referencia |
| `speed` | float | `1.0` | Aceptado pero no tiene efecto directo |
| `emotion` | string | `null` | No soportado directamente |
| `temperature` | float | `0.8` | Controla la variabilidad de la voz (0.0–1.0) |
| `top_p` | float | `0.8` | Nucleus sampling del LLM (0.0–1.0) |

**Ejemplo de request:**

```json
{
  "text": "¡Bienvenidos a mi stream! Hoy vamos a jugar algo muy especial.",
  "voice": "casiopy",
  "temperature": 0.8,
  "top_p": 0.8
}
```

**Respuesta:**

```json
{
  "ok": true,
  "audio_b64": "<base64 WAV>",
  "sample_rate": 44100,
  "duration_s": 5.2,
  "generation_time_s": 34.1,
  "rtf": 6.56,
  "backend": "fish-speech-local"
}
```

> El sample rate de **44100 Hz** produce la mayor calidad de audio entre todos los servicios disponibles.

**Decodificar el audio en Python:**

```python
import base64

audio_bytes = base64.b64decode(response["audio_b64"])
with open("salida.wav", "wb") as f:
    f.write(audio_bytes)
```

---

## Parámetros de inferencia avanzados

Los parámetros internos de `ServeTTSRequest` están configurados así:

| Parámetro | Valor | Descripción |
|---|---|---|
| `chunk_length` | 200 | Longitud de chunk para inferencia |
| `repetition_penalty` | 1.1 | Penaliza repeticiones en el LLM |
| `max_new_tokens` | 1024 | Máximo de tokens generados |
| `stream` | False | Modo no-streaming (respuesta completa) |

---

## Notas técnicas

- **Venv aislado obligatorio.** `protobuf==3.19.6` es incompatible con `protobuf>=4.x` que usan otros servicios. **No compartas el entorno virtual.**
- **Sin transcript necesario.** Fish Speech realiza clonación zero-shot con solo el audio de referencia.
- **LLM-based = mayor latencia.** El modelo procesa el texto como un LLM antes de sintetizar. Esto explica tanto la alta calidad como el RTF elevado (~6.56).
- **`compile=False` en Windows.** `torch.compile()` tiene problemas en Windows y está desactivado.
- **`half=False`.** El modelo corre en float32 para mayor estabilidad.
- **`temperature` y `top_p`.** Controlan la variabilidad vocal del LLM. Valores más altos producen más variación expresiva pero pueden reducir la inteligibilidad. Para voz consistente, usa valores bajos (0.5–0.7).
