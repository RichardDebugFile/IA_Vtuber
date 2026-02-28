# IA_Vtuber — Casiopy

Asistente virtual VTuber modular con síntesis de voz personalizada (fine-tune MeloTTS), conversación por IA (Ollama) y avatar 2D animado. Cada componente corre como microservicio independiente y se gestiona desde un dashboard web centralizado.

---

## Arquitectura

```
Micrófono
    │
    ▼
 STT (8803) ──────────────────────────────────────────────────┐
                                                               │
                                                               ▼
Avatar 2D ◄────── Face Service (8804)          Conversation (8801) ◄──► Ollama
(2D simple)                │                          │
                           │                          ▼
                           │                    Assistant (8802)
                           │                          │
                           └──────────────────────────┤
                                                       ▼
                                               TTS Router (8810)
                                              /    |    |    \
                                     Casiopy OpenV Cosy Fish Qwen3
                                      (8815) (8811)(8812)(8814)(8813)

Monitoring Dashboard (8900)  ──── controla todos los servicios
```

---

## Inicio rápido

### 1. Instalar dependencias del monitoring service

```bash
cd services/monitoring-service
pip install -r requirements.txt   # o: pip install fastapi uvicorn httpx
```

### 2. Iniciar el dashboard

```bash
# Windows
services/monitoring-service/start.bat

# O directamente
cd services/monitoring-service
uvicorn src.main:app --host 127.0.0.1 --port 8900
```

### 3. Abrir el dashboard

```
http://127.0.0.1:8900
```

Desde ahí puedes iniciar, detener y monitorizar todos los servicios sin usar la línea de comandos.

---

## Requisitos

| Requisito | Versión mínima | Notas |
|-----------|---------------|-------|
| Python | 3.10+ | Cada servicio tiene su propio venv |
| Ollama | última | Para el LLM de conversación (`gemma3` por defecto) |
| GPU NVIDIA | 8 GB VRAM | Recomendado para TTS neural; CPU funciona pero muy lento |
| Windows 10/11 | — | Scripts `.bat` para arranque; los `.py` son multiplataforma |

---

## Servicios

Ver [services/README.md](services/README.md) para la descripción completa y el mapa de puertos.

| Puerto | Servicio | Estado |
|--------|----------|--------|
| **8900** | Monitoring Dashboard | ✅ Core |
| **8800** | Gateway HTTP | ✅ Core |
| **8801** | Conversation (LLM) | ✅ Core |
| **8802** | Assistant (orquestador) | ✅ Core |
| **8803** | STT — Faster-Whisper | ✅ Activo |
| **8804** | Face Service 2D | ✅ Activo |
| **8805** | TTS Blips | ✅ Activo |
| **8810** | TTS Router (gateway de voz) | ✅ Activo |
| **8815** | TTS Casiopy ★ DEFAULT | ✅ Activo |
| **8811** | TTS OpenVoice V2 | ✅ Activo |
| **8812** | TTS CosyVoice3 | ✅ Activo |
| **8813** | TTS Qwen3 | ✅ Activo |
| **8814** | TTS Fish Speech | ✅ Activo |
| **8820** | Memory Service — API | ✅ Activo |
| **11434** | Ollama (externo) | — |

---

## Síntesis de voz

Todas las peticiones de síntesis pasan por el **TTS Router (8810)**. Nunca accedas directamente a un backend TTS en producción.

```bash
# Ejemplo: sintetizar con el backend por defecto (Casiopy)
curl -X POST http://127.0.0.1:8810/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola, soy Casiopy!", "mode": "casiopy"}'
```

El backend Casiopy usa un modelo fine-tuneado de MeloTTS con la voz de la VTuber.
El entrenamiento y los scripts de dataset están en [`finetune-melotts/`](finetune-melotts/) y [`dataset/`](dataset/).

### Muestras de audio

Ejemplos reales generados por cada backend (click → reproductor de GitHub):

| Backend | Muestra |
|---------|---------|
| Casiopy ★ fine-tune (DEFAULT) | [🔊 casiopy.wav](samples/casiopy.wav) |
| OpenVoice V2 | [🔊 openvoice.wav](samples/openvoice.wav) |
| CosyVoice3 | [🔊 cosyvoice.wav](samples/cosyvoice.wav) |
| Qwen3-TTS | [🔊 qwen3.wav](samples/qwen3.wav) |
| Fish Speech | [🔊 fish.wav](samples/fish.wav) |

---

## Variables de entorno

El archivo `.env` de la raíz y los `.env` de cada servicio configuran URLs y modelos. Los más relevantes:

| Variable | Defecto | Descripción |
|----------|---------|-------------|
| `GATEWAY_HTTP` | `http://127.0.0.1:8800` | URL del gateway |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Servidor Ollama |
| `OLLAMA_MODEL` | `gemma3` | Modelo LLM |

---

## Estructura del repositorio

```
IA_Vtuber/
├── services/           # Todos los microservicios
│   ├── monitoring-service/   # Dashboard de control (empezar aquí)
│   ├── tts-router/           # Gateway único de síntesis de voz
│   ├── tts-casiopy/          # Backend de voz principal (fine-tune)
│   ├── conversation/         # Motor de conversación (LLM)
│   ├── assistant/            # Orquestador de servicios
│   ├── stt/                  # Speech-to-Text
│   ├── face-service-2D-simple/ # Avatar 2D
│   └── memory-service/       # Memoria a largo plazo (PostgreSQL)
├── finetune-melotts/   # Pipeline de entrenamiento de la voz
├── dataset/            # Generación y gestión del dataset de audio
└── configs/            # Configuración global
```

---

## Contribución

1. Haz un fork del repositorio y crea una rama con tu cambio.
2. Envía un Pull Request describiendo claramente tus modificaciones.
3. Asegúrate de que los cambios pasen las pruebas y respeten el estilo del proyecto.
