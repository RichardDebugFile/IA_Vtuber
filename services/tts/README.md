# TTS Microservice

Este microservicio genera audio a partir del texto utilizando un modelo de [Fish Audio](https://huggingface.co/fishaudio). Puede consumir mensajes del microservicio de conversación y expone una API HTTP preparada para integrarse con otros componentes.

## Instalación del modelo
Descarga el modelo de Fish Audio en la carpeta `models`:
```bash
mkdir -p models
# Ejemplo usando un modelo publicado en HuggingFace
git clone https://huggingface.co/fishaudio/fish-speech-1.4 models/fish-speech
```

## Ejecución
```bash
python -m uvicorn src.server:app --host 127.0.0.1 --port 8802 --app-dir src
```

El endpoint principal es `POST /speak` que recibe `{ "text": "hola" }` y devuelve un JSON con la respuesta, emoción detectada y el audio codificado en base64.
