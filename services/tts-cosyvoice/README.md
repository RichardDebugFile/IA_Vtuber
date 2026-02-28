# tts-cosyvoice

Servicio wrapper de **CosyVoice3** (modelo `Fun-CosyVoice3-0.5B`) que expone una API HTTP para síntesis de voz con clonación zero-shot. Este servicio clona la voz a partir de un audio de referencia y, opcionalmente, su transcripción para mayor fidelidad.

---

## Créditos

| Componente | Repositorio | Organización | Licencia |
|---|---|---|---|
| **CosyVoice3** | [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) | Alibaba / FunAudioLLM | Apache 2.0 |
| **Matcha-TTS** | [shivammehta25/Matcha-TTS](https://github.com/shivammehta25/Matcha-TTS) | Shivam Mehta | MIT |
| **Fun-CosyVoice3-0.5B** | [FunAudioLLM/CosyVoice3-0.5B (HuggingFace)](https://huggingface.co/FunAudioLLM/CosyVoice3-0.5B) | FunAudioLLM | Apache 2.0 |

---

## Entorno de prueba

| Parámetro | Valor |
|---|---|
| Sistema operativo | Windows 11 Pro (build 26200) |
| GPU | NVIDIA RTX 5060 Ti (Blackwell, sm_120, 12 GB VRAM) |
| CUDA | 12.8 |
| Python | 3.12 |
| PyTorch | 2.7.0+cu128 |
| transformers | **4.51.3** (versión fija — no actualizar a 5.x) |
| numpy | 1.26.4 |
| RTF medido | ~3.76 (texto ~160 chars → 8.9s de audio) |
| VRAM utilizada | ~6 GB (LLM en float32 por compatibilidad Blackwell) |

> **RTF (Real-Time Factor):** RTF = tiempo de generación / duración del audio. RTF < 1 es más rápido que tiempo real; RTF > 1 es más lento.

---

## Advertencias importantes

### GPU Blackwell (RTX 5000 series, sm_120)

El LLM interno de CosyVoice3 usa `bfloat16` por defecto, lo que produce salidas con valores NaN en GPUs Blackwell (arquitectura sm_120). El servidor **corrige esto automáticamente** convirtiendo el LLM a `float32` al cargarlo. Esto es necesario para obtener audio coherente.

### Versión de transformers

`transformers >= 5.x` produce audio incoherente con este modelo. El archivo `requirements.txt` fija exactamente `transformers==4.51.3`. **No actualices esta dependencia.**

---

## Cómo funciona

### Modo Zero-Shot (con transcript — mayor calidad)

Si la carpeta de la voz contiene un par `.wav` + `.txt` con el mismo nombre, el servicio usa **zero-shot cloning**:

- El transcript del audio de referencia se pasa junto con el audio.
- El modelo aprende a reproducir la voz a partir de ambos.
- Requiere que el texto en `.txt` coincida **exactamente** con lo que se dice en el audio.

### Modo Cross-Lingual (solo audio — menor calidad)

Si la carpeta solo tiene `.wav` sin `.txt`, el servicio usa **cross-lingual cloning**:

- Solo se usa el speaker embedding del audio de referencia.
- Menor fidelidad en la clonación pero funciona sin necesidad de transcript.

---

## Estructura del servicio

```
tts-cosyvoice/
├── server.py               # Servicio FastAPI (puerto 8812)
├── start.bat               # Script de inicio
├── setup_venv.bat          # Configuración del entorno virtual
├── requirements.txt        # Dependencias Python
├── outputs/                # Audios generados por los tests
├── venv/                   # Entorno virtual local (generado)
└── repo/                   # Repositorio CosyVoice (clonado localmente)
    ├── cosyvoice/          # Módulo Python principal
    ├── third_party/
    │   └── Matcha-TTS/     # Dependencia de síntesis acústica (submódulo)
    ├── pretrained_models/
    │   └── Fun-CosyVoice3-0.5B/   # Pesos del modelo
    │       ├── llm.pt              # LLM principal (Qwen2-based)
    │       ├── CosyVoice-BlankEN/  # Config del tokenizer
    │       └── ...
    └── tools/
```

---

## Instalación paso a paso

### Requisitos previos

- Python 3.12 ([python.org](https://www.python.org/downloads/))
- CUDA 12.8

---

### Paso 1 — Clonar CosyVoice3

El repositorio usa submódulos (Matcha-TTS). El flag `--recursive` es **obligatorio**:

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git repo
```

Esto creará `repo/cosyvoice/`, `repo/third_party/Matcha-TTS/`, etc.

---

### Paso 2 — Descargar el modelo Fun-CosyVoice3-0.5B

Desde Hugging Face:

```
https://huggingface.co/FunAudioLLM/CosyVoice3-0.5B
```

Con `huggingface-cli`:

```bash
pip install huggingface-hub
huggingface-cli download FunAudioLLM/CosyVoice3-0.5B --local-dir repo/pretrained_models/Fun-CosyVoice3-0.5B
```

O usando el script incluido en el repositorio:

```bash
python repo/download_cosyvoice3.py
```

La estructura esperada:

```
repo/pretrained_models/Fun-CosyVoice3-0.5B/
├── llm.pt
├── flow.pt
├── hift.pt
├── speech_tokenizer_v2.onnx
└── CosyVoice-BlankEN/
    ├── config.json
    ├── generation_config.json
    └── vocab.json
```

---

### Paso 3 — Configurar el entorno virtual

```
setup_venv.bat
```

**Instalación manual alternativa:**

```bash
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
```

> **Critico:** `requirements.txt` fija `transformers==4.51.3` y `numpy==1.26.4`. No actualices estas dependencias o el audio generado será incoherente.

---

### Paso 4 — Preparar el audio de referencia

Para la mayor calidad (modo zero-shot), proporciona un par `.wav` + `.txt` con el mismo nombre de archivo:

```
services/tts/reference/
└── casiopy/
    ├── CasiopyVoz-5s.wav    # Audio de referencia (3–8 segundos ideal)
    └── CasiopyVoz-5s.txt    # Transcripción EXACTA del audio
```

Si solo hay `.wav`, el servicio usará modo cross-lingual automáticamente.

> **Importante:** El texto en `.txt` debe coincidir exactamente con lo que se dice en el audio (incluyendo pausas, muletillas, etc.).

---

## Arrancar el servicio

```
start.bat
```

O manualmente:

```bash
venv\Scripts\python server.py
```

El servidor arranca en `http://127.0.0.1:8812`. La carga del modelo tarda ~15–30 segundos.

Verifica el estado:

```
GET http://127.0.0.1:8812/health
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
  "backend": "cosyvoice3",
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
| `speed` | float | `1.0` | Velocidad de habla (0.5–2.0) |
| `emotion` | string | `null` | No tiene efecto en este servicio |

**Ejemplo de request:**

```json
{
  "text": "Buenos días, bienvenidos a mi stream de hoy.",
  "voice": "casiopy",
  "speed": 1.0
}
```

**Respuesta:**

```json
{
  "ok": true,
  "audio_b64": "<base64 WAV>",
  "sample_rate": 24000,
  "duration_s": 3.2,
  "generation_time_s": 12.0,
  "rtf": 3.76,
  "backend": "cosyvoice3",
  "mode": "zero_shot"
}
```

El campo `mode` indica el modo usado: `"zero_shot"` (con transcript) o `"cross_lingual"` (sin transcript).

**Decodificar el audio en Python:**

```python
import base64

audio_bytes = base64.b64decode(response["audio_b64"])
with open("salida.wav", "wb") as f:
    f.write(audio_bytes)
```

---

## Notas técnicas

- **Venv aislado obligatorio.** `numpy==1.26.4` y `transformers==4.51.3` son incompatibles con otros servicios TTS. No compartas el entorno virtual.
- **LLM en float32.** El servidor convierte automáticamente el LLM a `float32` para evitar NaN en Blackwell. Esto aumenta el uso de VRAM a ~6 GB (en lugar de ~4 GB en float16).
- **TF32 desactivado.** `torch.backends.cuda.matmul.allow_tf32 = False` y `torch.backends.cudnn.allow_tf32 = False` son necesarios para estabilidad en Blackwell.
- **Sample rate fijo.** CosyVoice3 genera audio a 24000 Hz.
