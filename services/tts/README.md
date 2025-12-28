
# VTuber TTS (FishAudio) — Guía de instalación y uso (Windows / PowerShell)

> Esta guía deja **dos entornos separados**:
> - **fish-speech** (servidor HTTP del modelo) con su propio venv: `.fs`
> - **IA_Vtuber/services/tts** (microservicio / cliente y tooling) con su venv: `venv`
>
> El CLI del microservicio **auto‑enciende** el servidor de fish cuando está apagado, leyendo rutas desde `.env`.

---

## Rutas de ejemplo usadas a lo largo de la guía
Ajusta a las tuyas si difieren:
```
FISH_REPO = F:\Documentos F\GitHub\IA_Vtuber\services\tts\vendor\fish-speech
FISH_VENV_PY = F:\Documentos F\GitHub\IA_Vtuber\services\tts\vendor\fish-speech\.fs\Scripts\python.exe
FISH_CKPT = F:\Documentos F\GitHub\IA_Vtuber\services\tts\models\openaudio-s1-mini
FISH_TTS_HTTP = http://127.0.0.1:8080/v1/tts
```

---

# A) Instalar **fish-speech** (servidor)

> Todo lo siguiente se hace **dentro de `FISH_REPO`** y crea el venv **`.fs`** allí.
> El `requirements.txt` de **fish** debe guardarse **en ese repo** (no en IA_Vtuber).

### 1) Preparar venv limpio de Python 3.10
```powershell
# (opcional) borrar venv anterior
deactivate 2>$null
cd "F:\Documentos F\GitHub\IA_Vtuber\services\tts\vendor\fish-speech"
If (Test-Path .\.fs) { Remove-Item -Recurse -Force .\.fs }

# crear venv y activar
py -3.10 -m venv .fs
.\.fs\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel
```

### 2) Crear `requirements.txt` (en **fish-speech**) y **instalar**
Contenido recomendado (ajustado a lo que probamos):
```
--extra-index-url https://download.pytorch.org/whl/cu121

# CUDA / PyTorch (cu121)
torch==2.5.1+cu121
torchvision==0.20.1+cu121
torchaudio==2.5.1+cu121

# Pins críticos
numpy==1.26.4
einx[torch]==0.2.2
vector-quantize-pytorch==1.14.6
fsspec==2024.2.0

# Server HTTP y utilidades
fastapi==0.116.1
uvicorn[standard]==0.35.0
loguru
httpx
ormsgpack
pyrootutils
kui
baize
soundfile
rich
natsort

# Configuración / audio
hydra-core==1.3.2
omegaconf==2.3.0
opencc-python-reimplemented==0.1.7
librosa==0.10.1
resampy==0.4.3
descript-audiotools
descript-audio-codec

# Lightning (el server importa ambos)
lightning==2.1.2
pytorch-lightning==2.1.2
lightning-utilities==0.10.1
torchmetrics==1.3.2

# Validaciones / tokenizador / compresión
pydantic==2.9.2
tiktoken==0.11.0
cachetools==6.2.0
zstandard==0.24.0
loralib==0.1.2

# Hugging Face stack
transformers==4.45.2
tokenizers==0.20.1
huggingface_hub==0.25.2
safetensors>=0.4.5
sentencepiece>=0.1.99
```

Instalar todo:
```powershell
pip install -r .\requirements.txt
```

### 3) Verificar CUDA / versiones
```powershell
python -c "import torch, importlib.metadata as md, numpy as np; print('CUDA?', torch.cuda.is_available()); print('torch', torch.__version__, 'CUDA', torch.version.cuda); print('numpy', np.__version__); print('einx', md.version('einx'))"
```

### 4) Descargar el checkpoint **OpenAudio S1‑Mini**
> Debes terminar con **`config.json`** y **`codec.pth`** dentro de `FISH_CKPT`.

Opción 1 — usando `huggingface_hub` (recomendado; reemplaza `<REPO_ID>` por el correcto, p. ej. `fishaudio/openaudio-s1-mini` si aplica):
```powershell
python - << 'PY'
from huggingface_hub import snapshot_download
import shutil, os
repo_id = "<REPO_ID>"  # EJEMPLO: "fishaudio/openaudio-s1-mini"
dst = r"F:\Documentos F\GitHub\IA_Vtuber\services\tts\models\openaudio-s1-mini"
os.makedirs(dst, exist_ok=True)
local = snapshot_download(repo_id=repo_id, allow_patterns=["*config*.json","*codec*.pth","*.json","*.pth"])
for f in os.listdir(local):
    if f.endswith((".json",".pth")):
        shutil.copy2(os.path.join(local,f), dst)
print("copiado a:", dst)
PY
```

Opción 2 — ya tienes los archivos: simplemente colócalos en:
```
F:\Documentos F\GitHub\IA_Vtuber\services\tts\models\openaudio-s1-mini\
  ├─ config.json
  └─ codec.pth
```

### 5) Arrancar el servidor HTTP de fish
```powershell
$CKPT="F:\Documentos F\GitHub\IA_Vtuber\services\tts\models\openaudio-s1-mini"
python -m tools.api_server --listen 0.0.0.0:8080 --llama-checkpoint-path "$CKPT" --decoder-checkpoint-path "$CKPT\codec.pth" --decoder-config-name modded_dac_vq
```
> Dejar esta ventana abierta (o usar el auto‑start del microservicio, ver sección C).

### 6) Prueba rápida del endpoint
```powershell
python -c "import httpx,ormsgpack,pathlib; u='http://127.0.0.1:8080/v1/tts'; b={'text':'(joyful) Hola, esto es una prueba.','format':'wav'}; h={'Content-Type':'application/msgpack'}; r=httpx.post(u, content=ormsgpack.packb(b), headers=h, timeout=600); print('HTTP', r.status_code, r.headers.get('content-type'), 'bytes', len(r.content)); pathlib.Path('fish_test.wav').write_bytes(r.content)"
Get-Item .\fish_test.wav | Format-List Name,Length,LastWriteTime
start .\fish_test.wav
```

---

# B) Configurar **IA_Vtuber/services/tts** (microservicio / cliente)

### 1) Instalar dependencias del proyecto principal
```powershell
cd "F:\Documentos F\GitHub\IA_Vtuber"
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel
pip install -r .\requirements.txt   # (requirements del proyecto raíz)
# extras necesarios para el CLI/HTTP:
pip install python-dotenv ormsgpack simpleaudio
```

### 2) Crear `.env`
Puedes ubicarlo en **`services/tts/.env`** o en la **raíz del repo**. El código detecta ambos.
```
FISH_REPO=F:\Documentos F\GitHub\IA_Vtuber\services\tts\vendor\fish-speech
FISH_VENV_PY=F:\Documentos F\GitHub\IA_Vtuber\services\tts\vendor\fish-speech\.fs\Scripts\python.exe
FISH_CKPT=F:\Documentos F\GitHub\IA_Vtuber\services\tts\models\openaudio-s1-mini
FISH_TTS_HTTP=http://127.0.0.1:8080/v1/tts
```

### 3) Probar sin levantar servidores propios
```powershell
cd .\services\tts
# Prueba directa al endpoint HTTP
python -m src.probe_tts --text "Esto es una prueba de voz en español." --emotion joyful --out _out\joyful.wav
start .\_out\joyful.wav
```

### 4) CLI con **auto‑start** del server fish
El CLI arranca automáticamente el servidor de fish si no está arriba (lee rutas del `.env`):
```powershell
python -m src.cli "hola mundo" --emotion happy --backend http
```
- Si el server está caído → lo inicia (`tools.api_server`) y espera `/health`.
- Si quieres desactivar el auto‑start: `--no-autostart`.

### 5) Servidor FastAPI del microservicio (puerto 8802)
```powershell
cd .\services\tts
python -m uvicorn src.server:app --host 127.0.0.1 --port 8802 --app-dir src
```
`POST /speak` → `{ "text": "hola" }` → `{ reply, emotion, audio_b64 }`.

### 6) Utilidades extra
- Diagnóstico integral:
  ```powershell
  python -m src.diag --deep
  ```
- Bench simple (requiere conversation si lo usas end‑to‑end):
  ```powershell
  python - << 'PY'
  import anyio
  from src.performance import TTSPerformance
  from src.engine import TTSEngine
  from src.conversation_client import ConversationClient
  async def main():
      perf = TTSPerformance(engine=TTSEngine(), conv=ConversationClient())
      t = await perf.run("Prueba de latencia")
      print("segundos:", t)
  anyio.run(main)
  PY
  ```

---

# C) Gestionar el server de fish desde el microservicio

Hemos añadido `src/fish_server.py` (gestor local) con **pidfile** y **logs**:

- **Estado**
  ```powershell
  python -m src.fish_server --status
  ```

- **Arrancar manualmente** (lee rutas de `.env` si no pasas flags):
  ```powershell
  python -m src.fish_server --start
  ```
  O usar el comando con logs:
  ```powershell
  python -m src.fish_server --start --timeout 360 --log ""
  ``` 
  - **Comando para probar manualmente el microservicio**:
  ```powershell
  python -m src.cli "Hola, probando mi VOZ FIJA" --emotion happy --backend http --out test_ref.wav
  ``` 

- **Detener siempre** (aunque se haya iniciado desde el CLI): 
  ```powershell
  python -m src.fish_server --stop
  ```

- Archivos:
  - PID: `services/tts/.run/fish_api.pid`
  - Logs: `services/tts/.logs/fish_api.log`

---

# Recomendaciones

- **GPU**: con RTX 3080 10 GB va bien. Cierra apps que usen VRAM antes de generar. (Se estima que este microservicio usa de 5 a 6 GB de VRAM)
- **Evita mezclar** dependencias: mantén `.fs` (fish) y `venv` (microservicio) por separado.
- Si ves `HTTP 422` al llamar `/v1/tts`, recuerda que el server espera **MessagePack** (`Content-Type: application/msgpack`). Usa `ormsgpack` como en los ejemplos.
- Si ves `ConnectError 10061`, el server no está arriba. El CLI con `--backend http` lo **auto‑enciende** si tu `.env` tiene `FISH_REPO`, `FISH_VENV_PY`, `FISH_CKPT`.
- Para ejecutar comandos multi‑línea en PowerShell, usa **una sola línea** o el backtick `` ` `` al final de cada línea.
- Si cambias el puerto, actualiza `FISH_TTS_HTTP` en el `.env`.

---

## Chequeo rápido final (mini checklist)
1. `.fs` creado en **fish-speech** y `pip install -r requirements.txt` hecho ✅  
2. `config.json` y `codec.pth` presentes en **FISH_CKPT** ✅  
3. `.env` creado (en raíz o `services/tts`) con `FISH_REPO`, `FISH_VENV_PY`, `FISH_CKPT`, `FISH_TTS_HTTP` ✅  
4. `python -m src.cli "hola" --emotion happy --backend http` genera WAV ✅  
5. `python -m src.fish_server --stop` detiene el server cuando quieras ✅

