# IA_Vtuber

Proyecto modular orientado a crear un asistente virtual con capacidad de conversación, generación de voz y monitoreo del escritorio. Cada componente se implementa como microservicio para facilitar el desarrollo y la experimentación.

## Requisitos

- Python 3.10 o superior
- `pip` para instalar dependencias
- (Opcional) PowerShell y Make para scripts de desarrollo

## Instalación

1. Clona este repositorio.
2. Crea y activa un entorno virtual:
   - En PowerShell:
     ```powershell
     py -3.10 -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - En Bash:
     ```bash
     python3.10 -m venv venv
     source venv/bin/activate
     ```
3. Instala las dependencias principales:
   ```bash
   pip install -r requirements.txt
   ```
4. Descarga el modelo de voz de [Fish Audio](https://huggingface.co/fishaudio) dentro de `services/tts/models`.
   Ejemplo:
   ```bash
   mkdir -p services/tts/models
   git clone https://huggingface.co/fishaudio/fish-speech-1.4 services/tts/models/fish-speech
   ```
   Este repositorio no incluye el modelo por su tamaño. El servicio `tts` buscará el modelo en la ruta anterior.

5. Activa/instala Ollama con el modelo de lenguaje deseado
   ```bash
   ollama run "modelo_deseado"
   ```
   Nota: en este repositorio se usó gemma3 (comando de ejemplo para ello: ollama run gemma3)

## Uso

### Iniciar microservicios
Cada servicio se ejecuta con [Uvicorn](https://www.uvicorn.org/) desde su carpeta:

#### Interfaz gráfica (modelo Vtuber)
```bash
cd apps/desktop-pet-qt/src
python  main.py  
```

#### gateway (puerto 8765)
```bash
cd services/gateway
python -m uvicorn src.main:app --host 127.0.0.1 --port 8765 --app-dir src
```

#### conversation (puerto 8801)
```bash
cd services/conversation
python -m uvicorn src.server:app --host 127.0.0.1 --port 8801 --app-dir src
```

#### affect (por implementar)
```bash
cd services/affect
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

#### asr (por implementar)
```bash
cd services/asr
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

#### desktopctl (por implementar)
```bash
cd services/desktopctl
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

#### screenwatch (por implementar)
```bash
cd services/screenwatch
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

#### assistant (puerto 8810)
```bash
cd services/assistant
python -m uvicorn src.server:app --host 127.0.0.1 --port 8810 --app-dir src
```

#### tts (puerto 8080 y 8802)
Genera audio a partir del texto respondiendo con el servicio de conversación.
Es necesario haber descargado previamente el modelo de Fish Audio en cualquier parte del dispostivo y ejecutarlo para que exponga su puerto y luego en `services/tts/models` guardar el openaudio-s1-mini (para más información, leer el README.md del microservicio de "tts").

```bash
cd services/tts
python -m src.fish_server --start
python -m uvicorn src.server:app --host 127.0.0.1 --port 8802 --app-dir src
```

Luego para detener de ser necesario:

```bash
python -m src.fish_server --stop
```

#### Comandos para probar los microservicios

### Probar desde PowerShell - Microservicio de Conversación
Ejemplo de petición al servicio de conversación 

```powershell
Invoke-RestMethod -Uri http://localhost:8801/chat -Method Post -Body (@{text = 'Hola'} | ConvertTo-Json) -ContentType 'application/json'
```

### Probar desde PowerShell - Microservicio de TTS
Ejemplo de petición al servicio de tts:

```powershell
python -m src.cli "hola" --emotion happy --backend http
```

### Probar desde PowerShell - Microservicio de Assistant
Ejemplo de petición al servicio de IA y tts:

```powershell
curl.exe -X POST "http://127.0.0.1:8810/api/assistant/aggregate" -H "Content-Type: application/json" --data '{"text":"Hola", "out":"url"}'
# -> {"audio_url":"/media/<id>.wav", ...}
```




### Variables de entorno
Los servicios leen un archivo `.env` para configurar parámetros. El microservicio de conversación reconoce las siguientes variables:

* `GATEWAY_HTTP`: URL del gateway para publicar eventos (por defecto `http://127.0.0.1:8765`).
* `OLLAMA_HOST`: dirección del servidor Ollama que genera las respuestas (por defecto `http://127.0.0.1:11434`).
* `OLLAMA_MODEL`: nombre del modelo usado por Ollama (por defecto `gemma3`).
* `CONVERSATION_HTTP`: (servicio `tts`) URL del microservicio de conversación (por defecto `http://127.0.0.1:8801`).

Exporta estas variables antes de iniciar los servicios si necesitas valores distintos.

## Contribución

Las contribuciones son bienvenidas. Si encuentras un problema o deseas mejorar el proyecto:

1. Haz un fork del repositorio y crea una rama con tu cambio.
2. Envía un Pull Request describiendo claramente tus modificaciones.
3. Asegúrate de que los cambios pasen las pruebas y respeten el estilo del proyecto.
