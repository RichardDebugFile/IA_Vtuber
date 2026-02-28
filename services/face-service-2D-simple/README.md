# Face Service 2D Simple

Servicio de "cara" para la VTuber Casiopy - Aplicación de overlay de escritorio con avatar 2D animado que responde a emociones en tiempo real.

## Descripción

Este servicio proporciona la representación visual de la VTuber mediante una ventana overlay (siempre visible) con un avatar 2D que:
- Cambia expresiones faciales según la emoción detectada
- Muestra burbujas de diálogo con el texto hablado
- Se integra con el gateway mediante WebSocket para recibir eventos en tiempo real
- Es completamente interactivo (arrastrable, escalable, configurable)

## Arquitectura

```
┌─────────────────────────────────────────┐
│   Face Service 2D Simple (PySide6/Qt)  │
│                                         │
│  ┌────────────┐      ┌───────────────┐ │
│  │  Overlay   │      │    Avatar     │ │
│  │  Window    │◄─────┤    Image      │ │
│  └────┬───────┘      └───────────────┘ │
│       │                                 │
│  ┌────▼────────┐     ┌───────────────┐ │
│  │   Text      │     │  WS Client    │ │
│  │   Bubble    │     │  (Threading)  │ │
│  └─────────────┘     └───────┬───────┘ │
│                              │         │
└──────────────────────────────┼─────────┘
                               │
                               ▼
                    Gateway WebSocket
                    (ws://127.0.0.1:8800/ws)
```

## Características Principales

### 1. **Overlay de Escritorio**
- Ventana semi-transparente siempre visible
- Sin bordes, click-through parcial
- Compatible con Windows (DirectX/OpenGL)

### 2. **Sistema de Emociones**
- 16+ expresiones configurables
- Cambio de emoción en tiempo real desde el gateway
- Navegación manual con teclas `[` y `]`
- Acceso directo con números `1-9`

### 3. **Burbujas de Diálogo**
- Texto con fondo semi-transparente
- Posición configurable (arriba, abajo, izq, der)
- Auto-dimensionado según contenido
- Renderizado con fuentes personalizadas

### 4. **Controles Interactivos**
- **Arrastrar**: Click izquierdo + drag para mover
- **Escalar**: Ctrl + scroll o Ctrl + `+`/`-`
- **Menú**: Click derecho para opciones
- **Emociones**: `[` y `]` para navegar, `1-9` para directa

### 5. **Integración WebSocket**
- Cliente WS en hilo separado (thread-safe)
- Recibe eventos `emotion` y `utterance` del gateway
- Actualiza UI mediante señales Qt

## Estructura del Proyecto

```
services/face-service-2D-simple/
├── src/
│   ├── main.py                 # Punto de entrada
│   ├── overlay_window.py       # Ventana overlay
│   ├── avatar/
│   │   ├── avatar_config.py    # Configuración YAML
│   │   └── avatar_image.py     # Render del avatar
│   ├── ui/
│   │   ├── bubble.py           # Burbuja de texto
│   │   └── tray.py             # System tray (futuro)
│   ├── ipc/
│   │   ├── ws_client.py        # Cliente WebSocket
│   │   ├── qt_signals.py       # Puente thread-safe
│   │   └── messages.py         # Modelos de mensajes
│   ├── native/
│   │   └── win/
│   │       └── window_flags.py # Flags nativos de Windows
│   └── assets/
│       └── avatars/
│           └── default/
│               ├── avatar.yaml # Configuración del avatar
│               ├── emotion_X.png # Imágenes por emoción
│               └── bubble/     # Assets de burbujas
├── run_gui.py                  # Launcher
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Instalación

### Requisitos
- Python 3.10+
- Sistema operativo: Windows (recomendado), Linux, macOS

### Instalar Dependencias

```bash
cd services/face-service-2D-simple
pip install -e .

# O manualmente
pip install PySide6>=6.7 pydantic>=2.7 websockets>=12.0 PyYAML>=6.0
```

## Uso

### Iniciar el Servicio

```bash
# Desde la raíz del proyecto
python services/face-service-2D-simple/run_gui.py

# O desde el directorio del servicio
cd services/face-service-2D-simple
python run_gui.py
```

### Variables de Entorno

```bash
# URL del WebSocket del gateway
export GATEWAY_WS="ws://127.0.0.1:8800/ws"
```

### Controles

| Acción | Control |
|--------|---------|
| **Mover ventana** | Click izquierdo + drag |
| **Zoom in** | Ctrl + `+` o Ctrl + scroll arriba |
| **Zoom out** | Ctrl + `-` o Ctrl + scroll abajo |
| **Reset zoom** | Ctrl + `0` |
| **Menú contextual** | Click derecho |
| **Siguiente emoción** | `]` |
| **Emoción anterior** | `[` |
| **Emoción directa** | Teclas `1` a `9` |
| **Cerrar** | Menú → Cerrar |

## Configuración del Avatar

El avatar se configura mediante `src/assets/avatars/default/avatar.yaml`:

```yaml
emotions:
  neutral: emotion_neutral.png
  happy: emotion_happy.png
  sad: emotion_sad.png
  excited: emotion_excited.png
  # ... más emociones

bubble:
  max_width: 400           # Ancho máximo del texto
  font_size: 18            # Tamaño de fuente
  color: "#FFFFFF"         # Color de fondo
  text_color: "#1e1e1e"    # Color del texto
  opacity: 0.95            # Opacidad (0.0-1.0)
  position: "top"          # top, bottom, left, right
  margin:
    x: 20                  # Margen horizontal
    y: 20                  # Margen vertical
  offset:
    x: 0                   # Desplazamiento X
    y: -50                 # Desplazamiento Y
```

## Integración con el Ecosistema

### Eventos Recibidos (desde Gateway)

#### 1. Evento `emotion`
```json
{
  "topic": "emotion",
  "data": {
    "label": "happy"
  }
}
```
**Efecto**: Cambia la expresión del avatar a "happy"

#### 2. Evento `utterance`
```json
{
  "topic": "utterance",
  "data": {
    "text": "¡Hola! ¿Cómo estás?"
  }
}
```
**Efecto**: Muestra el texto en la burbuja de diálogo

### Flujo de Integración

```
┌─────────────┐
│ Conversation│
│  Service    │
│             │
│ Emotion:    │
│ "happy"     │
└──────┬──────┘
       │
       ▼
┌──────────────┐      ┌─────────────────┐
│   Gateway    │──ws──►│  Face Service  │
│              │      │                 │
│ Topics:      │      │ Updates:        │
│ - emotion    │      │ - Avatar expr   │
│ - utterance  │      │ - Text bubble   │
└──────────────┘      └─────────────────┘
```

## Detalles Técnicos

### Tecnologías Usadas

- **PySide6 (Qt 6)**: Framework de UI
  - `QGraphicsView/Scene`: Sistema de renderizado 2D
  - `QTimer`: Loop de actualización
  - Signals/Slots para thread-safety

- **websockets**: Cliente WebSocket asíncrono en threading

- **PyYAML**: Configuración del avatar

- **Pydantic**: Validación de configuración

### Threading Model

```
┌──────────────────────────────────────┐
│         Main Thread (Qt GUI)         │
│                                      │
│  ┌────────────┐  ┌────────────────┐ │
│  │  Render    │  │ Event Handler  │ │
│  │  Avatar    │  │ (user input)   │ │
│  └────────────┘  └────────────────┘ │
│         ▲                            │
│         │ Qt Signals (thread-safe)   │
│         │                            │
└─────────┼────────────────────────────┘
          │
┌─────────┼────────────────────────────┐
│         │  Background Thread         │
│  ┌──────┴─────────┐                  │
│  │  WS Client     │                  │
│  │  (websockets)  │                  │
│  └────────────────┘                  │
└──────────────────────────────────────┘
```

Los eventos del WebSocket se emiten como señales Qt que son procesadas de forma thread-safe por el hilo principal de la GUI.

### Ventana Overlay

La ventana usa flags específicos para comportarse como overlay:
- **Windows**: `WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST`
- **Linux**: Window hints de Qt para "always on top"
- **Transparencia**: Alpha channel + compositing

## Personalización

### Añadir Nuevas Emociones

1. Crear imagen PNG transparente: `src/assets/avatars/default/emotion_nombre.png`
2. Agregar a `avatar.yaml`:
   ```yaml
   emotions:
     nombre: emotion_nombre.png
   ```
3. El servicio detectará automáticamente la nueva emoción

### Cambiar Fuente de la Burbuja

Colocar archivo `.ttf` en `src/assets/fonts/` y actualizar en `main.py`:
```python
panel = TextPanel(
    win.scene,
    font_path="assets/fonts/mifuente.ttf",  # Ruta a tu fuente
    font_size=18,
    ...
)
```

## Troubleshooting

### La ventana no aparece siempre en frente
- **Windows**: Verificar que el proceso no está bloqueado por políticas de siempre visible
- **Linux**: Instalar compositor (compton, picom) para transparencia

### El WebSocket no conecta
- Verificar que el gateway está corriendo en `ws://127.0.0.1:8800/ws`
- Revisar logs en consola para errores de conexión
- Comprobar firewall/antivirus

### Imágenes no cargan
- Verificar rutas en `avatar.yaml` relativas a la carpeta del avatar
- Comprobar que las imágenes son PNG con transparencia
- Revisar permisos de lectura de archivos

### Alto consumo de CPU
- Reducir el framerate del timer (actualmente 33ms ~30fps)
- Optimizar tamaño de imágenes del avatar
- Cerrar ventanas de debugging si están abiertas

## Roadmap

- [ ] System tray icon para ocultar/mostrar
- [ ] Configuración de hotkeys personalizables
- [ ] Soporte para avatares Live2D
- [ ] Animaciones de transición entre emociones
- [ ] Lip-sync básico con audio
- [ ] Multi-monitor support
- [ ] Temas de burbujas personalizables

## Licencia

Parte del proyecto IA_Vtuber

---

**Nota**: Este es el servicio de "cara" básico 2D. Para versiones más avanzadas (3D, Live2D, VRM), consultar otros servicios face-service-*.
