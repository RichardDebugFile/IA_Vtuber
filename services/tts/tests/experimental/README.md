# Experimental Code

Código experimental archivado que NO está en uso actualmente en producción.

## Contenido

### `conversation_tts.py`

Engine experimental de TTS con streaming por oraciones.

**Características:**
- Streaming de audio por oraciones (en lugar de audio completo)
- Procesamiento paralelo de múltiples chunks
- Predicción de tiempos de generación
- Caché de frases comunes
- Segmentación inteligente por comas

**Estado:** Archivado (no integrado al servidor principal)

**Por qué no se usa:**
- El servidor usa directamente `engine_http.py` para síntesis completa
- La latencia de red hace que el streaming por oraciones no sea ventajoso
- Complejidad adicional sin beneficio medible

**Utilidad futura:**
- Puede ser útil si se implementa streaming WebSocket en el futuro
- Contiene lógica interesante de segmentación de texto
- Predictor de tiempos puede ser útil para optimizaciones

## Cómo Usar (si se necesita)

```python
from tests.experimental.conversation_tts import ConversationTTS
from src.engine_http import HTTPFishEngine

# Crear engine base
base_engine = HTTPFishEngine()

# Wrap con streaming
streaming_engine = ConversationTTS(base_engine, max_parallel=2)

# Usar streaming
async for chunk in streaming_engine.synthesize_streaming(text, emotion):
    # Reproducir chunk.audio_bytes
    pass
```

## Notas

- Este código fue desarrollado durante experimentos de optimización
- No tiene tests unitarios
- Puede requerir ajustes para funcionar con versiones actuales
- Ver historial de git para contexto completo
