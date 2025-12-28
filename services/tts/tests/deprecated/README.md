# Deprecated Code

Código deprecado que ha sido reemplazado por implementaciones mejores.

## Contenido

### `fish_client_casiopy.py`

Cliente TTS específico para la voz de Casiopy.

**Estado:** DEPRECADO - Usar `src.engine_http.HTTPFishEngine` en su lugar

**Por qué está deprecado:**
- `engine_http.py` es más genérico y flexible
- Hardcodeaba la voz de Casiopy en el código
- No soportaba el sistema de presets de emociones
- Duplicaba funcionalidad ya disponible en el engine principal

**Migración:**

```python
# ANTES (deprecado)
from tests.deprecated.fish_client_casiopy import CasiopyTTSClient
client = CasiopyTTSClient()
client.synthesize("Hola", "output.wav")

# DESPUÉS (usar esto)
from src.engine_http import HTTPFishEngine
engine = HTTPFishEngine()
audio = engine.synthesize("Hola", emotion="neutral")
```

## Por qué mantener este código

- Referencia histórica
- Puede contener lógica de parámetros específicos que valga la pena revisar
- Documentación de decisiones de diseño

## Próximos Pasos

Este código puede ser eliminado completamente si:
1. No hay dependencias externas que lo usen
2. Han pasado > 6 meses sin uso
3. La funcionalidad está completamente cubierta por `engine_http.py`
