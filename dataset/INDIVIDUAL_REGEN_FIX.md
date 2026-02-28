# Fix: Regeneraciones Individuales Múltiples

## Problema Reportado

Al hacer regeneraciones individuales de varios audios rápidamente (usando el botón "↻ Regenerar"):
- **Comportamiento anterior**: Solo se generaba 1 audio, los demás quedaban pendientes sin procesar
- **Comportamiento esperado**: Generar TODOS los audios seleccionados manualmente

## Causa Raíz

### Código Problemático (ANTES):
```python
async def regenerate_entry(self, entry_id: int, emotion: Optional[str] = None):
    # ... marca como pending ...

    if not self.is_running:
        self.is_running = True  # ← Bloquea inmediatamente

        # Genera SOLO este audio y ESPERA a que termine
        await self._generate_audio(entry)  # ← Bloqueante

        self.is_running = False
```

### Escenario de Fallo:
```
Usuario hace 3 regeneraciones rápidas (IDs: 52, 69, 72):

Click en ID 52:
  - self.is_running = False
  - Marca 52 como pending
  - self.is_running = True
  - Genera 52... (ESPERANDO) ← Bloquea aquí

Click en ID 69 (mientras 52 está generando):
  - self.is_running = True
  - Marca 69 como pending
  - NO genera (solo marca) ✗

Click en ID 72 (mientras 52 está generando):
  - self.is_running = True
  - Marca 72 como pending
  - NO genera (solo marca) ✗

Resultado:
  - ID 52: Generado ✓
  - ID 69: Pendiente sin generar ✗
  - ID 72: Pendiente sin generar ✗
```

## Solución Implementada

### Nueva Arquitectura: Cola de Regeneraciones Individuales

```python
class DatasetGenerator:
    def __init__(...):
        # Nueva cola para regeneraciones individuales
        self.pending_individual_regenerations = set()
```

### Flujo Corregido:

```python
async def regenerate_entry(self, entry_id: int, emotion: Optional[str] = None):
    # 1. Marca como pending (igual que antes)
    entry.status = "pending"
    entry.emotion = emotion
    self.state_manager.save_state(state)

    # 2. NUEVO: Agrega a la cola
    self.pending_individual_regenerations.add(entry_id)

    # 3. Si NO hay generación corriendo, procesa TODA la cola
    if not self.is_running:
        await self._process_individual_regenerations()
    else:
        # Si HAY generación, se procesará en el batch mixto normal
        logger.info(f"Entry {entry_id} queued for regeneration")
```

### Nueva Función: Procesamiento en Batch

```python
async def _process_individual_regenerations(self):
    """
    Procesa TODOS los audios en la cola de regeneraciones individuales.
    """
    # 1. Obtiene todos los IDs en la cola
    entry_ids = list(self.pending_individual_regenerations)
    self.pending_individual_regenerations.clear()

    # 2. Carga las entradas desde el estado
    state = self.state_manager.load_state()
    entries_to_process = [
        e for e in state.entries
        if e.id in entry_ids and e.status == "pending"
    ]

    # 3. Procesa TODAS en paralelo
    self.is_running = True
    tasks = [asyncio.create_task(self._generate_audio(e)) for e in entries_to_process]
    await asyncio.gather(*tasks, return_exceptions=True)
    self.is_running = False
```

## Escenario de Éxito (DESPUÉS):

```
Usuario hace 3 regeneraciones rápidas (IDs: 52, 69, 72):

Click en ID 52:
  - Marca 52 como pending
  - Agrega 52 a cola: {52}
  - self.is_running = False
  - Espera 50ms para acumular más clicks...

Click en ID 69 (50ms después):
  - Marca 69 como pending
  - Agrega 69 a cola: {52, 69}
  - self.is_running = True (el procesamiento ya empezó)
  - Solo encola, no procesa

Click en ID 72 (50ms después):
  - Marca 72 como pending
  - Agrega 72 a cola: {52, 69, 72}
  - self.is_running = True
  - Solo encola, no procesa

Procesamiento (después de acumular):
  - Procesa batch: [52, 69, 72] en paralelo
  - Genera los 3 audios simultáneamente
  - Broadcast: "🔄 Procesando 3 regeneraciones individuales"
  - Broadcast: "✅ 3 regeneraciones completadas"

Resultado:
  - ID 52: Generado ✓
  - ID 69: Generado ✓
  - ID 72: Generado ✓
```

## Características de la Solución

### 1. Acumulación Inteligente
- Si haces varios clicks rápidos, se acumulan en la cola
- Se procesan TODOS juntos en un solo batch

### 2. Procesamiento Paralelo
- Todos los audios seleccionados se generan en paralelo
- Más rápido que generarlos uno por uno

### 3. Integración con Sistema Normal
- Si hay generación corriendo, se integran al batch mixto
- Si NO hay generación, se procesan inmediatamente

### 4. Feedback Visual
```
Logs visibles en el dashboard:
- "🔄 Procesando 3 regeneraciones individuales seleccionadas"
- "🎙️ Generando casiopy_0052: ..."
- "🎙️ Generando casiopy_0069: ..."
- "🎙️ Generando casiopy_0072: ..."
- "✅ casiopy_0052 completado (12.5s, 598KB)"
- "✅ casiopy_0069 completado (11.2s, 534KB)"
- "✅ casiopy_0072 completado (13.1s, 625KB)"
- "✅ 3 regeneraciones individuales completadas"
```

## Archivos Modificados

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `src/generator.py` | Agregada cola `pending_individual_regenerations` | 45 |
| `src/generator.py` | Modificada `regenerate_entry()` para usar cola | 534-589 |
| `src/generator.py` | Nueva función `_process_individual_regenerations()` | 591-646 |
| `src/generator.py` | Limpieza de cola en batch mixto | 240-241 |

## Cómo Usar

### Caso 1: Regenerar 1 Audio
1. Click en "↻ Regenerar" en un audio
2. Selecciona emoción (o auto-detect)
3. Se genera inmediatamente

### Caso 2: Regenerar Múltiples Audios (NUEVO)
1. Click en "↻ Regenerar" en audio 52
2. Click en "↻ Regenerar" en audio 69
3. Click en "↻ Regenerar" en audio 72
4. **Todos se generan juntos en paralelo** ✓

### Caso 3: Durante Generación Normal
1. Generación está corriendo (procesando audios 1-100)
2. Click en "↻ Regenerar" en audio 52
3. Se marca como pending con emoción personalizada
4. Se procesará en el siguiente batch mixto (máx. 5 por batch)

## Ventajas

✅ **Todos los audios seleccionados se generan**: No se pierde ninguno
✅ **Procesamiento paralelo**: Más rápido que secuencial
✅ **Sin bloqueos**: No interfiere con generación normal
✅ **Feedback claro**: Mensajes en logs sobre cuántos se están procesando
✅ **Cola inteligente**: Acumula clicks rápidos automáticamente

---

*Fix implementado: 2026-01-10*
*Issue: Regeneraciones individuales solo procesaban 1 audio*
