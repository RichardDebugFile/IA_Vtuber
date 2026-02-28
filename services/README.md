# services/

Directorio raíz de todos los microservicios del proyecto. Cada carpeta es un servicio independiente con su propio README detallado.

---

## Mapa de puertos

> **Regla:** Ningún servicio nuevo debe usar un puerto ya asignado. Consulta esta tabla antes de añadir servicios.

| Puerto | Servicio | Carpeta |
|--------|----------|---------|
| **8800** | Gateway | `gateway/` |
| **8801** | Conversation AI | `conversation/` |
| **8802** | Assistant | `assistant/` |
| **8803** | STT (Speech-to-Text) | `stt/` |
| **8804** | Face Service 2D | `face-service-2D-simple/` |
| **8805** | TTS Blips | `tts-blips/` |
| **8806** | TTS Service (legacy) | `tts/` |
| **8810** | TTS Router | `tts-router/` |
| **8811** | TTS OpenVoice V2 | `tts-openvoice/` |
| **8812** | TTS CosyVoice3 | `tts-cosyvoice/` |
| **8813** | TTS Qwen3-TTS | `tts-qwen3/` |
| **8814** | TTS Fish Speech (local) | `tts-fish/` |
| **8820** | Memory — API | `memory-service/` |
| **8821** | Memory — PostgreSQL | `memory-service/` |
| **8822** | Memory — ChromaDB | `memory-service/` |
| **8900** | Monitoring Service | `monitoring-service/` |
| **8080** | Fish Audio Server (Docker) | — externo — |
| **11434** | Ollama (LLM) | — externo — |

---

## Servicios implementados

### Núcleo

| Carpeta | Puerto | Descripción |
|---------|--------|-------------|
| `gateway/` | 8800 | Punto de entrada HTTP del sistema. Enruta peticiones externas al servicio correcto. |
| `conversation/` | 8801 | Motor de conversación de la IA. Gestiona el historial y genera respuestas mediante el LLM. |
| `assistant/` | 8802 | Capa de asistente. Orquesta los módulos de percepción, conversación y salida. |
| `monitoring-service/` | 8900 | Dashboard web para monitorizar, iniciar y detener el resto de servicios. |

### Audio — Entrada

| Carpeta | Puerto | Descripción |
|---------|--------|-------------|
| `stt/` | 8803 | Speech-to-Text con Faster-Whisper. Transcribe el audio del micrófono en tiempo real. |

### Audio — Salida (TTS)

| Carpeta | Puerto | Descripción |
|---------|--------|-------------|
| `tts-router/` | 8810 | **Punto de entrada único para síntesis de voz.** Gestiona el ciclo de vida de cada backend TTS y enruta las peticiones al backend activo. |
| `tts-openvoice/` | 8811 | Backend OpenVoice V2 — RTF ~1.44. Recomendado para respuestas en tiempo real (streaming rápido). |
| `tts-cosyvoice/` | 8812 | Backend CosyVoice3 — RTF ~3.76. Mayor calidad de clonación de voz (streaming ocasional). |
| `tts-qwen3/` | 8813 | Backend Qwen3-TTS — RTF ~7.74. Para creación de contenido/datasets. Más lento. |
| `tts-fish/` | 8814 | Backend Fish Speech — RTF ~6.56, 44100 Hz. Mayor fidelidad de audio. |
| `tts-blips/` | 8805 | Sonidos de "blips" sincronizados con el habla (efecto de diálogo estilo Animal Crossing). |
| `tts/` | 8806 | TTS Service heredado (OpenVoice con docker-ngc). Mantenido por compatibilidad. |

### Percepción visual

| Carpeta | Puerto | Descripción |
|---------|--------|-------------|
| `face-service-2D-simple/` | 8804 | Avatar 2D de la VTuber. Renderiza la cara y sincroniza expresiones con el audio. |

### Memoria

| Carpeta | Puerto | Descripción |
|---------|--------|-------------|
| `memory-service/` | 8820 (API) · 8821 (DB) · 8822 (ChromaDB) | Memoria a largo plazo de la IA. Almacena y recupera conversaciones usando PostgreSQL + ChromaDB (vectores). |

---

## Servicios planificados (vacíos)

| Carpeta | Descripción prevista |
|---------|---------------------|
| `affect/` | Reconocimiento de emociones en audio/vídeo para modular la respuesta de la IA. |
| `asr/` | Módulo ASR alternativo o especializado (independiente del STT principal). |
| `screenwatch/` | Captura y análisis de pantalla para que la IA pueda "ver" lo que ocurre en el escritorio. |
| `desktopctl/` | Control del escritorio (mouse, teclado, ventanas) para la IA. |

---

## Servicios externos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Ollama | 11434 | Servidor LLM local. Gestiona los modelos de lenguaje usados por `conversation/`. |
| Fish Audio (Docker) | 8080 | Versión Docker de Fish Audio. Servicio legacy, reemplazado por `tts-fish/`. |
