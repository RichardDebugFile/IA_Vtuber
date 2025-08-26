# IA_Vtuber

## Iniciar microservicios
Cada servicio se ejecuta con [Uvicorn](https://www.uvicorn.org/) desde su carpeta:

### gateway (puerto 8765)
```bash
cd services/gateway
python -m uvicorn src.main:app --host 127.0.0.1 --port 8765 --app-dir src
```

### conversation (puerto 8801)
```bash
cd services/conversation
python -m uvicorn src.server:app --host 127.0.0.1 --port 8801 --app-dir src
```

### affect
```bash
cd services/affect
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

### asr
```bash
cd services/asr
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

### desktopctl
```bash
cd services/desktopctl
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

### screenwatch
```bash
cd services/screenwatch
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

### tts
```bash
cd services/tts
python -m uvicorn src.server:app --host 127.0.0.1 --port <PUERTO> --app-dir src
```

## Probar desde PowerShell
Ejemplo de petición al servicio de conversación:

```powershell
Invoke-RestMethod -Uri http://localhost:8801/chat -Method Post -Body (@{text = 'Hola'} | ConvertTo-Json) -ContentType 'application/json'
```

## Variables de entorno
Los servicios leen un archivo `.env` para configurar parámetros. El microservicio de conversación reconoce las siguientes variables:

* `GATEWAY_HTTP`: URL del gateway para publicar eventos (por defecto `http://127.0.0.1:8765`).
* `OLLAMA_HOST`: dirección del servidor Ollama que genera las respuestas (por defecto `http://127.0.0.1:11434`).
* `OLLAMA_MODEL`: nombre del modelo usado por Ollama (por defecto `gemma3`).

Exporta estas variables antes de iniciar los servicios si necesitas valores distintos.
