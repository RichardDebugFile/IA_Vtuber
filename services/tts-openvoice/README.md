# tts-openvoice

Servicio wrapper de **OpenVoice V2** que expone una API HTTP para síntesis de voz con clonación de timbre. Utiliza [MeloTTS](https://github.com/myshell-ai/MeloTTS) para la generación base en español y [OpenVoice ToneColorConverter](https://github.com/myshell-ai/OpenVoice) para transferir el timbre de una voz de referencia al audio sintetizado.

---

## Créditos

| Componente | Repositorio | Organización | Licencia |
|---|---|---|---|
| **OpenVoice V2** | [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice) | MyShell AI | MIT |
| **MeloTTS (ES)** | [myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS) | MyShell AI | MIT |

---

## Entorno de prueba

| Parámetro | Valor |
|---|---|
| Sistema operativo | Windows 11 Pro (build 26200) |
| GPU | NVIDIA RTX 5060 Ti (Blackwell, sm_120, 12 GB VRAM) |
| CUDA | 12.8 |
| Python | 3.12 |
| PyTorch | 2.7.0+cu128 |
| RTF medido | ~1.44 (texto ~160 chars → 10.7s de audio) |
| VRAM utilizada | ~3–4 GB |

> **RTF (Real-Time Factor):** RTF = tiempo de generación / duración del audio. RTF < 1 es más rápido que tiempo real; RTF > 1 es más lento.

---

## Cómo funciona

1. **MeloTTS** genera el audio base en español con la voz estándar del modelo.
2. **ToneColorConverter** extrae el timbre (speaker embedding) del audio de referencia.
3. El timbre de referencia se aplica al audio base → resultado con la voz clonada.

El audio de referencia solo necesita ser un archivo `.wav`. No se requiere transcripción.

---

## Estructura del servicio

```
tts-openvoice/
├── server.py               # Servicio FastAPI (puerto 8811)
├── start.bat               # Script de inicio
├── setup_venv.bat          # Configuración del entorno virtual
├── requirements.txt        # Dependencias Python
├── test_tts.py             # Test local directo (sin servidor)
├── outputs/                # Audios generados por los tests
├── venv/                   # Entorno virtual local (generado)
└── repo/
    ├── OpenVoice/          # Código fuente de OpenVoice V2 (instalado editable)
    │   └── openvoice/      # Módulo Python principal
    └── checkpoints_v2/     # Pesos del modelo
        ├── converter/
        │   ├── config.json
        │   └── checkpoint.pth
        └── base_speakers/
            └── ses/
                ├── es.pth          # Speaker embedding base (español)
                ├── en-us.pth
                └── ...
```

---

## Instalación paso a paso

### Requisitos previos

- Python 3.12 ([python.org](https://www.python.org/downloads/))
- CUDA 12.8 (GPU NVIDIA recomendada; funciona en CPU con mayor latencia)

---

### Paso 1 — Clonar el repositorio OpenVoice V2

Desde la raíz del servicio (`services/tts-openvoice/`), ejecuta:

```bash
mkdir repo
cd repo
git clone https://github.com/myshell-ai/OpenVoice.git
cd ..
```

La estructura resultante debe ser `repo/OpenVoice/openvoice/`.

---

### Paso 2 — Descargar los checkpoints del modelo

Los checkpoints se descargan desde Hugging Face:

```
https://huggingface.co/myshell-ai/OpenVoice/tree/main/checkpoints_v2
```

Descarga la carpeta `checkpoints_v2` completa y colócala en `repo/`:

```
repo/checkpoints_v2/
├── converter/
│   ├── config.json
│   └── checkpoint.pth
└── base_speakers/
    └── ses/
        ├── es.pth
        ├── en-us.pth
        ├── en-au.pth
        ├── en-br.pth
        ├── en-india.pth
        ├── en-newest.pth
        ├── fr.pth
        ├── jp.pth
        ├── kr.pth
        └── zh.pth
```

Con `huggingface-cli` (recomendado):

```bash
pip install huggingface-hub
huggingface-cli download myshell-ai/OpenVoice --local-dir repo/checkpoints_v2 --include "checkpoints_v2/*"
```

---

### Paso 3 — Configurar el entorno virtual

Ejecuta el script de setup:

```
setup_venv.bat
```

El script intentará primero copiar un venv existente desde `D:\ExperimentosPython\TTS-Google\OpenVoice-V2\venv` (método rápido, si existe). Si no, instalará desde `requirements.txt`.

**Instalación manual alternativa:**

```bash
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
venv\Scripts\pip install -e repo\OpenVoice --no-deps
```

> **Nota:** La instalación de `melotts` descarga automáticamente los modelos de MeloTTS en español (~500 MB) la primera vez que se ejecuta. Se requiere conexión a internet.

---

### Paso 4 — Preparar el audio de referencia

Crea la carpeta de referencia para la voz que quieras usar:

```
services/tts/reference/
└── <nombre-de-voz>/
    └── muestra.wav          # Audio de referencia (5–30 segundos)
```

Ejemplo para la voz por defecto `casiopy`:

```
services/tts/reference/
└── casiopy/
    └── CasiopyVoz-15s.wav
```

El servicio buscará automáticamente cualquier `.wav` en esa carpeta. **No se necesita transcripción.**

---

## Arrancar el servicio

```
start.bat
```

O manualmente:

```bash
venv\Scripts\python server.py
```

El servidor arranca en `http://127.0.0.1:8811`. El modelo se carga en segundo plano al inicio (~10–15 segundos en GPU).

Puedes verificar el estado en:

```
GET http://127.0.0.1:8811/health
```

---

## API

### `GET /health`

Devuelve el estado del servicio. Siempre responde 200 (incluso mientras el modelo carga).

```json
{
  "ok": true,
  "model_loaded": true,
  "loading": false,
  "error": null,
  "backend": "openvoice-v2",
  "device": "cuda"
}
```

---

### `GET /voices`

Lista las voces disponibles (subcarpetas con `.wav` en el directorio de referencia).

```json
{"voices": ["casiopy", "otra-voz"]}
```

---

### `POST /synthesize`

Sintetiza texto con la voz indicada.

**Body (JSON):**

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `text` | string | requerido | Texto a sintetizar |
| `voice` | string | `"casiopy"` | Nombre de la voz de referencia |
| `speed` | float | `1.0` | Velocidad de habla (0.5–2.0) |
| `emotion` | string | `null` | No tiene efecto (OpenVoice no soporta control emocional nativo) |

**Ejemplo de request:**

```json
{
  "text": "Hola, ¿cómo estás? Espero que todo vaya bien.",
  "voice": "casiopy",
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
  "backend": "openvoice-v2"
}
```

El campo `audio_b64` contiene el audio en formato WAV codificado en Base64.

**Decodificar el audio en Python:**

```python
import base64

audio_bytes = base64.b64decode(response["audio_b64"])
with open("salida.wav", "wb") as f:
    f.write(audio_bytes)
```

---

## Notas técnicas

- **Sin control emocional.** OpenVoice V2 transfiere el timbre de la voz pero no modifica la emoción. El campo `emotion` se acepta pero no tiene efecto.
- **RTF ~1.44 en Blackwell.** El RTF está por encima de 1 en la GPU RTX 5060 Ti (Blackwell, sm_120). En GPUs de arquitecturas anteriores (Ampere, Ada Lovelace) el RTF típico es ≤ 0.74.
- **Caché de embeddings.** El speaker embedding de la voz de referencia se calcula solo la primera vez. Las peticiones siguientes con la misma voz son más rápidas.
- **Venv aislado.** Este servicio requiere su propio entorno virtual debido a versiones específicas de `melotts`, `openai-whisper` y otras dependencias.
