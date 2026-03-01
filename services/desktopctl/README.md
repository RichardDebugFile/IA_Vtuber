# Desktop Control Service — Casiopy

Servicio FastAPI que expone control del escritorio (mouse, teclado, ventanas,
captura de pantalla) y hotkeys globales para el sistema VTuber.
Permite que el gateway ordene acciones de UI en nombre de Casiopy.

## Puerto

`8807`

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `DESKTOPCTL_PORT` | `8807` | Puerto del servidor |
| `HOTKEY_PUSH_TO_TALK` | `<ctrl>+<space>` | Activar/desactivar STT |
| `HOTKEY_MUTE_TTS` | `<ctrl>+<shift>+m` | Silenciar/reanudar TTS |
| `HOTKEY_SHUTDOWN` | `<ctrl>+<shift>+q` | Apagar todos los servicios |
| `GATEWAY_URL` | `http://127.0.0.1:8800` | URL del gateway (para eventos de hotkeys) |

## Iniciar

```bash
cd services/desktopctl
# Usa el venv raíz del proyecto
../venv/Scripts/python -m uvicorn src.server:app --host 127.0.0.1 --port 8807
```

O desde monitoring-service / casiopy-app mediante el panel de control.

---

## Arquitectura

```
desktopctl (8807)
├── src/server.py          ← FastAPI: endpoints REST
├── src/ui_automation.py   ← wrapper puro: mouse, teclado, ventanas, screenshot
└── src/hotkeys.py         ← HotkeyManager: listener global en thread daemon
```

### Relación con el gateway

```
gateway (8800)
    └── POST /orchestrate/desktop  ──►  desktopctl:8807/action
                                         (acción compuesta para el LLM)
```

El gateway añade el endpoint `/orchestrate/desktop` que actúa como proxy
hacia este servicio, igual que `/orchestrate/stt` → `stt:8803`.

---

## Endpoints

### Sistema

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio + info de pantalla + hotkeys activos |

### Mouse

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `POST` | `/mouse/move` | `{x, y}` | Mover cursor |
| `POST` | `/mouse/click` | `{x, y, button?, clicks?}` | Click (left/right/middle) |
| `POST` | `/mouse/scroll` | `{x, y, dy}` | Scroll vertical |

### Teclado

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `POST` | `/keyboard/type` | `{text, interval?}` | Escribir texto |
| `POST` | `/keyboard/key` | `{key}` | Tecla especial (`"enter"`, `"ctrl+c"`, …) |
| `POST` | `/keyboard/hotkey` | `{keys: []}` | Combinación simultánea |

### Ventanas

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `GET` | `/windows` | — | Listar ventanas abiertas |
| `POST` | `/windows/focus` | `{title_pattern}` | Traer ventana al frente |
| `POST` | `/windows/minimize` | `{title_pattern}` | Minimizar ventana |
| `POST` | `/windows/maximize` | `{title_pattern}` | Maximizar ventana |
| `POST` | `/windows/close` | `{title_pattern}` | Cerrar ventana |

### Pantalla

| Método | Ruta | Params | Descripción |
|---|---|---|---|
| `GET` | `/screenshot` | `region=x,y,w,h` (opt.) | Captura en base64 PNG |
| `GET` | `/screen/size` | — | Resolución actual `{width, height}` |

### Hotkeys globales

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `GET` | `/hotkeys` | — | Listar hotkeys registrados |
| `POST` | `/hotkeys` | `{combo, description}` | Registrar hotkey → `{id}` |
| `DELETE` | `/hotkeys/{id}` | — | Deregistrar hotkey |

### Acción compuesta (para el LLM)

| Método | Ruta | Body | Descripción |
|---|---|---|---|
| `POST` | `/action` | `{type, ...params}` | Ejecuta click/type/key/window/screenshot en un solo call |

---

## Módulos

### `ui_automation.py`

Wrapper puro sobre `pynput` (mouse/teclado) y `pygetwindow` (ventanas Win32).
No tiene dependencias HTTP — es importable y testeable de forma aislada.

```python
# Mouse
mouse_move(x, y)
mouse_click(x, y, button="left", clicks=1)
mouse_scroll(x, y, dy)

# Teclado
keyboard_type(text, interval=0.0)
keyboard_key(key)           # "enter" | "esc" | "ctrl+c" | ...
keyboard_hotkey(*keys)      # keyboard_hotkey("ctrl", "shift", "s")

# Ventanas
list_windows() → list[dict]
focus_window(title_pattern) → bool
close_window(title_pattern) → bool
minimize_window(title_pattern) → bool
maximize_window(title_pattern) → bool

# Pantalla
screenshot(region=None) → str   # base64 PNG
get_screen_size() → dict        # {width, height}
```

### `hotkeys.py`

`HotkeyManager` gestiona un hilo daemon con `pynput.keyboard.GlobalHotKeys`.
Los hotkeys se disparan aunque el foco esté en otra ventana.

Hotkeys predefinidos (cargados en startup desde env):

| Combo | Efecto |
|---|---|
| `Ctrl+Space` | Publica evento `push-to-talk` en gateway WS |
| `Ctrl+Shift+M` | Publica evento `mute-tts` en gateway WS |
| `Ctrl+Shift+Q` | Publica evento `shutdown` en gateway WS |

---

## Integración en monitoring-service

Registrado en `SERVICES` con:
- `port: 8807`
- `color: "#FF5722"`
- `manageable: True`
- Sin dependencias obligatorias (`requires: []`)

---

## Tests

```bash
# Offline — no requiere servicios activos ni display
cd services/desktopctl
pytest tests/ -v
```

Los tests mockean `pynput` y `pygetwindow` para no necesitar GUI.

---

## Futuras extensiones

| Feature | Notas |
|---|---|
| `screenwatch` integration | Capturar + describir pantalla con VLM antes de actuar |
| Macros guardadas | `POST /macros` → secuencia de acciones reutilizable |
| Grabación de acciones | Registrar sesión de usuario → reproducir como macro |
