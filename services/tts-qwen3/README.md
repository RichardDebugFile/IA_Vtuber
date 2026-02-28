# tts-qwen3

Servicio wrapper de **Qwen3-TTS** (modelo `Qwen3-TTS-12Hz-0.6B-Base`) que expone una API HTTP para síntesis de voz con clonación mediante In-Context Learning (ICL) y x-vector. Desarrollado por el equipo Qwen de Alibaba.

---

## Créditos

| Componente | Enlace | Organización | Licencia |
|---|---|---|---|
| **Qwen3-TTS (modelo)** | [Qwen/Qwen3-TTS-12Hz-0.6B-Base (HuggingFace)](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) | Alibaba Qwen Team | Apache 2.0 |
| **qwen-tts (PyPI)** | [pypi.org/project/qwen-tts](https://pypi.org/project/qwen-tts/) | Alibaba | Apache 2.0 |

---

## Entorno de prueba

| Parámetro | Valor |
|---|---|
| Sistema operativo | Windows 11 Pro (build 26200) |
| GPU | NVIDIA RTX 5060 Ti (Blackwell, sm_120, 12 GB VRAM) |
| CUDA | 12.8 |
| Python | 3.12 |
| PyTorch | **2.10.0+cu128** (versión única — diferente al resto de servicios) |
| qwen-tts | 0.1.1 |
| RTF medido | ~7.74 (texto ~160 chars → 10.1s de audio) |
| VRAM utilizada | ~2–3 GB |
| Sample rate salida | 12000 Hz |

> **RTF (Real-Time Factor):** RTF = tiempo de generación / duración del audio. RTF < 1 es más rápido que tiempo real; RTF > 1 es más lento.

> **Importante:** Este servicio usa `torch==2.10.0+cu128`, **distinto** al resto de servicios TTS que usan `2.7.0`. Esto hace **obligatorio** tener un entorno virtual separado.

---

## Cómo funciona

### Modo ICL — In-Context Learning (con transcript — mayor calidad)

Si la carpeta de voz contiene un par `.wav` + `.txt` con el mismo nombre, el servicio usa **ICL (In-Context Learning)**:

- El modelo recibe el audio de referencia junto con su transcripción.
- Aprende a imitar la voz directamente desde el contexto proporcionado.
- Produce mayor fidelidad en la clonación.

### Modo x-vector (solo audio)

Si la carpeta solo tiene `.wav`, el servicio usa el **speaker embedding (x-vector)**:

- Se extrae un vector representativo de la voz del audio.
- Menor fidelidad que ICL pero no requiere transcripción.

En ambos casos, el resultado del análisis de la voz se **guarda en caché en memoria** para acelerar síntesis posteriores con la misma voz.

---

## Estructura del servicio

```
tts-qwen3/
├── server.py               # Servicio FastAPI (puerto 8813)
├── start.bat               # Script de inicio
├── setup_venv.bat          # Configuración del entorno virtual
├── requirements.txt        # Dependencias Python
├── outputs/                # Audios generados por los tests
├── venv/                   # Entorno virtual local (generado)
└── repo/
    └── models/
        └── Qwen3-TTS-12Hz-0.6B-Base/   # Pesos del modelo
            ├── model.safetensors
            ├── config.json
            ├── tokenizer_config.json
            ├── vocab.json
            ├── generation_config.json
            ├── preprocessor_config.json
            └── speech_tokenizer/
                ├── config.json
                ├── configuration.json
                ├── model.safetensors
                └── preprocessor_config.json
```

> A diferencia de los otros servicios, **no hay un repositorio de código fuente clonado** en `repo/`. El código del modelo se instala a través del paquete PyPI `qwen-tts`. La carpeta `repo/models/` contiene únicamente los pesos del modelo.

---

## Instalación paso a paso

### Requisitos previos

- Python 3.12 ([python.org](https://www.python.org/downloads/))
- CUDA 12.8

---

### Paso 1 — Descargar el modelo

El modelo se descarga desde Hugging Face:

```
https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
```

Crea la carpeta de destino y descarga con `huggingface-cli`:

```bash
pip install huggingface-hub
mkdir repo\models
huggingface-cli download Qwen/Qwen3-TTS-12Hz-0.6B-Base --local-dir repo\models\Qwen3-TTS-12Hz-0.6B-Base
```

La descarga incluye el modelo principal (~1.2 GB) y el speech tokenizer (~200 MB).

---

### Paso 2 — Configurar el entorno virtual

```
setup_venv.bat
```

**Instalación manual alternativa:**

```bash
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
```

> La versión `torch==2.10.0+cu128` es **específica de este servicio**. Si se mezcla con otro entorno que use `torch==2.7.0`, habrá conflictos de versión.

---

### Paso 3 — Preparar el audio de referencia

Para la mejor calidad (modo ICL), proporciona un par `.wav` + `.txt` con el mismo nombre:

```
services/tts/reference/
└── casiopy/
    ├── CasiopyVoz-15s.wav   # Audio de referencia (preferiblemente >10 segundos)
    └── CasiopyVoz-15s.txt   # Transcripción del audio
```

El servicio selecciona automáticamente el `.wav` de **mayor tamaño** (asumiendo que más grande = más duración = mejor referencia).

Si no hay `.txt`, el servicio usará modo x-vector automáticamente.

---

## Arrancar el servicio

```
start.bat
```

O manualmente:

```bash
venv\Scripts\python server.py
```

El servidor arranca en `http://127.0.0.1:8813`. La carga del modelo tarda ~20–30 segundos.

Verifica el estado:

```
GET http://127.0.0.1:8813/health
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
  "backend": "qwen3-tts",
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

**Body (JSON):**

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `text` | string | requerido | Texto a sintetizar |
| `voice` | string | `"casiopy"` | Nombre de la voz de referencia |
| `speed` | float | `1.0` | Velocidad de habla (aceptado pero no tiene efecto directo en este modelo base) |
| `emotion` | string | `null` | No soportado en el modelo base |

**Ejemplo de request:**

```json
{
  "text": "Hola a todos, bienvenidos al stream de hoy. Vamos a pasarla muy bien.",
  "voice": "casiopy",
  "speed": 1.0
}
```

**Respuesta:**

```json
{
  "ok": true,
  "audio_b64": "<base64 WAV>",
  "sample_rate": 12000,
  "duration_s": 4.1,
  "generation_time_s": 31.7,
  "rtf": 7.74,
  "backend": "qwen3-tts"
}
```

> **Nota:** El sample rate de salida es **12000 Hz** (más bajo que los demás servicios). El audio es inteligible y de buena calidad para voz, pero puede sonar menos brillante en altavoces de alta gama.

**Decodificar el audio en Python:**

```python
import base64

audio_bytes = base64.b64decode(response["audio_b64"])
with open("salida.wav", "wb") as f:
    f.write(audio_bytes)
```

---

## Notas técnicas

- **RTF ~7.74 — el más lento.** Este servicio no es adecuado para respuestas en tiempo real. Se recomienda para contenido pregrabado o síntesis en diferido.
- **Caché de voice prompt.** El `voice_clone_prompt` (embedding ICL o x-vector) se calcula una sola vez por voz y se guarda en memoria. Las síntesis siguientes con la misma voz arrancan directamente.
- **Idioma fijado a español.** El parámetro `language="Spanish"` está hardcodeado en la llamada a `generate_voice_clone()`.
- **Sin flash_attn en Windows.** Se usa `attn_implementation="sdpa"` (PyTorch SDPA) ya que Flash Attention no está disponible en Windows. El rendimiento es similar.
- **TF32 desactivado.** `torch.backends.cuda.matmul.allow_tf32 = False` para estabilidad numérica en Blackwell.
- **Venv aislado obligatorio.** La versión de PyTorch `2.10.0+cu128` es incompatible con la `2.7.0` que usan los demás servicios.
