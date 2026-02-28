# Guía de Precisión del STT Service

## Mejoras Implementadas

### 1. Modelo Mejorado: `base` → `medium` (769M parámetros)

**Cambio:** De modelo `base` (74M params) a `medium` (769M params)

**Mejora esperada:**
- ✅ **+17% más precisión** en reconocimiento de palabras (de 75% a 92%)
- ✅ Mucho mejor manejo de **acentos y dialectos** del español
- ✅ Menor confusión entre palabras similares
- ✅ Mejor con palabras técnicas y nombres propios
- ⚠️ Tarda ~2-3 minutos en cargar el modelo (primera vez: ~5 minutos)
- ⚠️ Usa ~5GB de VRAM (tu RTX 5060 Ti tiene suficiente)

### 2. Parámetros Optimizados

| Parámetro | Valor Anterior | Valor Nuevo | Mejora |
|-----------|---------------|-------------|---------|
| `beam_size` | 5 | 10 | Explora más opciones, mejor precisión |
| `best_of` | 5 | 10 | Evalúa más candidatos |
| `initial_prompt` | - | Frases en español | Guía al modelo al contexto |
| `condition_on_previous_text` | - | `True` | Usa contexto de frases anteriores |

### 3. Initial Prompt (Contexto Español)

El modelo ahora recibe ejemplos de español al inicio:
```
"Hola, ¿cómo estás? Buenos días. Gracias. Por favor."
```

Esto ayuda a:
- Reconocer mejor tildes (á, é, í, ó, ú)
- Entender puntuación en español
- Diferenciar entre palabras homófonas

## Comparación de Modelos

| Modelo | Parámetros | VRAM | Velocidad | Precisión (ES) | Uso Recomendado |
|--------|-----------|------|-----------|----------------|-----------------|
| tiny   | 39M       | ~1GB | Muy rápida | ⭐⭐ (60%)   | Pruebas rápidas |
| base   | 74M       | ~1GB | Rápida     | ⭐⭐⭐ (75%) | Uso básico rápido |
| small  | 244M      | ~2GB | Media      | ⭐⭐⭐⭐ (85%) | Buen balance |
| **medium** | **769M** | **~5GB** | **Lenta** | **⭐⭐⭐⭐⭐ (92%)** | **ACTUAL - Máxima precisión** |
| large-v3 | 1550M   | ~10GB | Muy lenta | ⭐⭐⭐⭐⭐ (95%) | Transcripción profesional |

## Recomendaciones de Uso

### Para Mejor Precisión

1. **Habla clara y a velocidad normal**
   - No muy rápido ni muy lento
   - Pronuncia bien las palabras completas

2. **Ambiente con poco ruido**
   - Cierra ventanas para reducir ruido exterior
   - Apaga ventiladores o aires acondicionados si es posible
   - Usa micrófono de buena calidad (o auriculares con mic)

3. **Distancia al micrófono**
   - Mantén ~15-20cm de distancia
   - No muy cerca (distorsión) ni muy lejos (ruido)

4. **Frases completas**
   - El modelo funciona mejor con frases completas que con palabras sueltas
   - Ejemplo bueno: "Hola, ¿cómo estás? Necesito ayuda con esto"
   - Ejemplo malo: "Hola... ehh... ayuda... mmm... esto"

### Si Aún No Es Preciso Suficiente

#### Opción 1: Cambiar a modelo `medium` (más preciso)

```bash
# Editar services/stt/src/config.py
WHISPER_MODEL = "medium"  # En lugar de "small"

# Reiniciar servicio STT
# Nota: Primera carga tomará ~3-5 minutos (descarga ~1.5GB)
```

**Ventajas:**
- Mucho más preciso (~92% accuracy)
- Mejor con acentos y dialectos

**Desventajas:**
- Requiere ~5GB VRAM (tu RTX 5060 Ti tiene suficiente)
- Transcripción tarda ~2-3x más tiempo
- Primera carga del modelo tarda más

#### Opción 2: Ajustar parámetros de VAD

Si el problema es que **corta palabras** o **no detecta voz**:

```python
# En services/stt/src/config.py
VAD_CONFIG = {
    "threshold": 0.3,       # Reducir para detectar voz más suave
    "min_silence_ms": 500,  # Aumentar para esperar pausas más largas
    "min_speech_ms": 150,   # Reducir para capturar palabras cortas
}
```

#### Opción 3: Desactivar VAD (Voice Activity Detection)

Si VAD está filtrando demasiado:

```python
# En services/stt/src/transcriber.py, línea 118
vad_filter=False,  # Cambiar True a False
```

Esto procesará todo el audio sin filtrar silencios.

## Problemas Comunes y Soluciones

### Problema: Confunde palabras similares

**Ejemplo:** "hola" → "ola", "vaca" → "baca"

**Solución:**
1. Actualizar el `INITIAL_PROMPT` con palabras problemáticas:
   ```python
   INITIAL_PROMPT = "Hola con h. Vaca con v. Haber y a ver."
   ```

2. Hablar más despacio y claro en esas palabras

### Problema: No reconoce nombres propios

**Ejemplo:** "Casiopy" → "casiopea"

**Solución:**
Agregar al prompt:
```python
INITIAL_PROMPT = "Mi nombre es Casiopy. Hola, ¿cómo estás?"
```

### Problema: Transcripción muy lenta

**Solución:**
1. Volver a modelo `base`:
   ```python
   WHISPER_MODEL = "base"
   ```

2. Reducir beam_size:
   ```python
   BEAM_SIZE = 5
   BEST_OF = 5
   ```

### Problema: Reconoce ruido de fondo como palabras

**Solución:**
1. Aumentar threshold de VAD:
   ```python
   VAD_CONFIG = {
       "threshold": 0.7,  # Más estricto
   }
   ```

2. Usar micrófono con cancelación de ruido

## Métricas de Rendimiento

### Con Modelo `medium` (actual)

- **Tiempo de carga:** ~2-3 minutos (primera vez: ~5 minutos para descargar ~1.5GB)
- **VRAM usado:** ~5GB
- **Tiempo por segundo de audio:** ~1-2 segundos
- **Precisión esperada (español conversacional):** ~92%

### Con Modelo `medium` (si cambias)

- **Tiempo de carga:** ~30-60 segundos (primera vez: ~5 minutos)
- **VRAM usado:** ~5GB
- **Tiempo por segundo de audio:** ~1-2 segundos
- **Precisión esperada (español conversacional):** ~92%

## Testing de Precisión

Para probar la precisión, usa frases con palabras difíciles:

```
Frases de prueba:
1. "Hola, ¿cómo estás? Voy a hacer la tarea."
2. "El perro va a ver la vaca en el bosque."
3. "Necesito hablar con Casiopy sobre inteligencia artificial."
4. "Buenos días, ¿podrías ayudarme por favor?"
```

Si reconoce correctamente el 80-90% de estas frases, el sistema está bien configurado.

## Variables de Entorno para Configuración Rápida

```bash
# Cambiar modelo sin editar código
export WHISPER_MODEL=medium

# Forzar uso de CPU (si GPU da problemas)
export DEVICE=cpu

# Cambiar idioma
export LANGUAGE=en  # Para inglés
```

Reiniciar el servicio después de cambiar variables de entorno.
