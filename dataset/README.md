# Dataset Generator - IA VTuber

Sistema de generación de dataset de audio para entrenamiento de voz de VTuber.

## Características

- **Generación Automática**: 2,000 clips de audio con texto variado en español
- **Múltiples Emociones**: 8 emociones distribuidas automáticamente (neutral, happy, sad, angry, fearful, surprised, disgusted, contemplative)
- **Procesamiento de Audio**: Normalización a -3dB, 24kHz, 16-bit, mono
- **Interfaz Web**: Dashboard en tiempo real con controles completos
- **Gestión de Estado**: Pausar, reanudar y continuar generación
- **Regeneración**: Regenerar audios con errores individualmente

## Requisitos Previos

1. **TTS Service** debe estar ejecutándose en `http://127.0.0.1:8802`
2. **Fish Speech** (Docker o servicio) debe estar disponible
3. Python 3.10+ con entorno virtual configurado

## Estructura del Proyecto

```
dataset/
├── src/                     # Código fuente
│   ├── main.py             # Aplicación FastAPI
│   ├── models.py           # Modelos Pydantic
│   ├── generator.py        # Motor de generación
│   ├── content_generator.py # Generador de texto
│   ├── tts_client.py       # Cliente TTS
│   ├── audio_processor.py  # Procesamiento de audio
│   ├── state_manager.py    # Persistencia de estado
│   └── websocket_manager.py # Gestión WebSocket
├── static/                  # Interfaz web
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── wavs/                    # Audios generados (2000 archivos)
├── metadata.csv             # Textos y emociones (2000 entradas)
├── generation_state.json    # Estado de generación
├── requirements.txt         # Dependencias Python
├── generate_metadata.py     # Script para generar metadata
└── start.bat               # Lanzador del servicio
```

## Instalación

### 1. Instalar Dependencias

Desde la carpeta `dataset/`:

```bash
..\..\venv\Scripts\pip.exe install -r requirements.txt
```

### 2. Generar Metadata (Opcional)

Si quieres regenerar el contenido de texto:

```bash
..\..\venv\Scripts\python.exe generate_metadata.py
```

Esto crea `metadata.csv` con 2,000 entradas de texto con emociones.

## Uso

### Inicio Rápido

1. **Ejecutar el servicio**:
   ```bash
   start.bat
   ```

2. Se abrirá automáticamente el navegador en `http://127.0.0.1:8801`

3. **Primera vez - Inicializar**:
   - Haz clic en "Inicializar Dataset"
   - Esto carga las 2,000 entradas desde `metadata.csv`

4. **Verificar servicios**:
   - Asegúrate de que TTS Service y Fish Speech estén en verde
   - Si están en rojo, inicia esos servicios primero

5. **Iniciar generación**:
   - Haz clic en "▶ Iniciar"
   - El sistema generará los audios en paralelo (4 workers por defecto)

### Controles Durante la Generación

- **⏸ Pausar**: Pausa temporalmente la generación
- **▶ Reanudar**: Continúa la generación pausada
- **⏹ Detener**: Detiene completamente (puedes reiniciar después)

### Gestión de Errores

- Los audios con error se marcan en rojo
- Haz clic en el botón "↻" para regenerar individualmente
- Los errores se registran en `generation_state.json`

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Interfaz web principal |
| `/api/status` | GET | Estado actual y estadísticas |
| `/api/entries` | GET | Lista de entradas (paginada) |
| `/api/start` | POST | Iniciar generación |
| `/api/pause` | POST | Pausar generación |
| `/api/resume` | POST | Reanudar generación |
| `/api/stop` | POST | Detener generación |
| `/api/regenerate` | POST | Regenerar entrada específica |
| `/api/audio/{filename}` | GET | Streaming de audio |
| `/api/services` | GET | Estado de TTS y Fish |
| `/api/initialize` | POST | Inicializar dataset |
| `/ws` | WebSocket | Actualizaciones en tiempo real |

## Especificaciones de Audio

Cada archivo generado cumple con:

- **Formato**: WAV
- **Sample Rate**: 24kHz
- **Bit Depth**: 16-bit PCM
- **Canales**: Mono (1 canal)
- **Normalización**: -3dB peak
- **Duración**: 3-10 segundos
- **Naming**: `casiopy_0001.wav` a `casiopy_2000.wav`

## Distribución de Emociones

La generación automática distribuye emociones según:

| Emoción | Porcentaje |
|---------|-----------|
| neutral | 30% |
| happy | 20% |
| sad | 10% |
| angry | 8% |
| fearful | 8% |
| surprised | 12% |
| disgusted | 7% |
| contemplative | 5% |

## Contenido de Texto

El sistema genera textos variados en español en 8 categorías:

1. **Saludos** (10%): "¡Hola! ¿Cómo estás?", "Buenos días"...
2. **Preguntas** (20%): "¿Me puedes ayudar?", "¿Qué opinas?"...
3. **Respuestas** (20%): "Claro, con gusto", "No estoy segura"...
4. **Emociones** (15%): "¡Qué emocionante!", "Me siento feliz"...
5. **Narración** (15%): "Había una vez...", "La historia comienza"...
6. **Comandos** (10%): "Por favor, haz esto", "Detente ahí"...
7. **Casual** (10%): "¿Viste la película?", "El clima está agradable"...
8. **Streaming**: Frases típicas de VTuber

## Progreso y Estadísticas

La interfaz muestra en tiempo real:

- **Total de clips**: 2,000
- **Completados**: Cantidad exitosa
- **Fallidos**: Cantidad con error
- **Duración total**: Tiempo acumulado de audio generado
- **Barra de progreso**: Porcentaje completado

## Estado Persistente

El archivo `generation_state.json` guarda:

- Estado actual (idle, running, paused, stopped, completed)
- Progreso de cada entrada
- Errores encontrados
- Metadata de audios generados

Esto permite **reanudar** la generación si se interrumpe.

## Troubleshooting

### TTS Service no está disponible
```bash
# Iniciar TTS Service primero en otro terminal
cd services/tts
start.bat
```

### Fish Speech no está disponible
```bash
# Iniciar Fish Speech Docker
cd services/tts/docker-ngc
docker-compose up -d
```

### Error al generar audio
- Verifica que ambos servicios estén funcionando
- Revisa los logs en la consola del servidor
- Usa el botón de regenerar (↻) para intentar de nuevo

### Problemas de memoria/VRAM
- Reduce `parallel_workers` en el código (default: 4)
- Editar en `src/main.py`, línea de `StartRequest`

## Desarrollo

### Ejecutar en modo desarrollo

```bash
cd F:\Documentos F\GitHub\IA_Vtuber\dataset
..\..\venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8801 --reload
```

### Logs

Los logs se muestran en la consola donde ejecutaste el servicio.

## Licencia

Parte del proyecto IA VTuber.

## Notas

- El dataset generado está en `wavs/` con 2,000 archivos
- Total esperado: 2-5 horas de audio
- Usa para entrenar modelos de síntesis de voz
- La calidad depende de los servicios TTS y Fish Speech
