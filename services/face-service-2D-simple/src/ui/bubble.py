from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsTextItem, QGraphicsPathItem
from PySide6.QtGui import QPainterPath, QPen, QBrush, QFont, QColor
from PySide6.QtCore import QRectF, QPointF, Qt, QTimer

def _qcolor(hex_str, default="#CDB4FF"):
    c = QColor(hex_str);  return c if c.isValid() else QColor(default)

class TextPanel(QGraphicsItemGroup):
    """Rectángulo redondeado (sin cola) con texto, con soporte de escala y efecto typewriter."""
    def __init__(self, scene, max_width=360, font_path=None, font_size=16,
                 bg_color="#CDB4FF", text_color="#1e1e1e", opacity=0.92):
        super().__init__()
        scene.addItem(self)
        self.max_width = max_width
        self.padding = 12
        self._padding_base = 12
        self._font_base_pt = font_size
        self._current_text = " "
        self.bg_color = _qcolor(bg_color)
        self.text_color = _qcolor(text_color, "#1e1e1e")
        self.opacity = opacity

        self.text = QGraphicsTextItem()
        self.text.setDefaultTextColor(self.text_color)
        f = QFont()
        if font_path: f.setFamily(font_path)
        f.setPointSize(self._font_base_pt)
        self.text.setFont(f)

        self.bg = QGraphicsPathItem()
        self.bg.setPen(QPen(Qt.transparent, 0))
        self.bg.setBrush(QBrush(self.bg_color))
        self.bg.setOpacity(self.opacity)

        self.addToGroup(self.bg); self.addToGroup(self.text)

        # Typewriter effect
        self._typewriter_timer = QTimer()
        self._typewriter_timer.timeout.connect(self._typewriter_tick)
        self._typewriter_full_text = ""
        self._typewriter_index = 0
        self._typewriter_speed = 50  # ms per character
        self._on_character_callback = None
        self._on_complete_callback = None

    def set_text(self, s: str):
        self._current_text = s if s else " "
        self.text.setTextWidth(self.max_width)
        self.text.setPlainText(self._current_text)
        r = self.text.boundingRect()
        w, h = r.width() + self.padding*2, r.height() + self.padding*2
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 12, 12)
        self.bg.setPath(path); self.text.setPos(self.padding, self.padding)

    def apply_scale(self, scale: float):
        """Escala padding, fuente y ancho máximo."""
        scale = max(0.5, min(3.0, float(scale)))
        self.padding = int(self._padding_base * scale)
        f = self.text.font(); f.setPointSize(int(self._font_base_pt * scale)); self.text.setFont(f)
        # max_width se ajusta desde main; aquí solo re-renderizamos:
        self.set_text(self._current_text)

    # ------- posicionamiento -------
    def place(self, position: str, avatar_item, margin_x=16, margin_y=16, extra_x=0, extra_y=0):
        position = (position or "overlay-bottom").lower()
        br = self.childrenBoundingRect(); w, h = br.width(), br.height()
        sr = self.scene().sceneRect()
        a = avatar_item.sceneBoundingRect()

        if position == "window-top-right":
            x = sr.right() - w - margin_x; y = sr.top() + margin_y
        elif position in ("overlay-bottom","overlay"):
            x = a.center().x() - w/2; y = a.bottom() - h - margin_y
        elif position == "overlay-top":
            x = a.center().x() - w/2; y = a.top() + margin_y
        elif position == "right":
            x = a.right() + margin_x; y = a.center().y() - h/2
        elif position == "left":
            x = a.left() - w - margin_x; y = a.center().y() - h/2
        elif position == "above":
            x = a.center().x() - w/2; y = a.top() - h - margin_y
        else:  # below
            x = a.center().x() - w/2; y = a.bottom() + margin_y

        # clamp dentro de la ventana
        x = max(sr.left(),  min(x, sr.right()  - w))
        y = max(sr.top(),   min(y, sr.bottom() - h))
        self.setPos(x + extra_x, y + extra_y)

    # ------- Typewriter effect -------
    def set_text_typewriter(self, full_text: str, speed_ms=50, on_character=None, on_complete=None):
        """Set text with typewriter effect (letra por letra).

        Args:
            full_text: El texto completo a mostrar
            speed_ms: Milisegundos entre cada letra (default: 50ms = 20 chars/sec)
            on_character: Callback llamado cada vez que aparece una letra nueva
            on_complete: Callback llamado cuando termina el efecto
        """
        # Stop any ongoing typewriter effect
        self._typewriter_timer.stop()

        self._typewriter_full_text = full_text if full_text else " "
        self._typewriter_index = 0
        self._typewriter_speed = max(1, int(speed_ms))
        self._on_character_callback = on_character
        self._on_complete_callback = on_complete

        # Start empty
        self.set_text("")

        # Start timer
        self._typewriter_timer.start(self._typewriter_speed)

    def _typewriter_tick(self):
        """Internal: display next character in typewriter effect."""
        if self._typewriter_index >= len(self._typewriter_full_text):
            # Finished
            self._typewriter_timer.stop()
            if self._on_complete_callback:
                self._on_complete_callback()
            return

        # Add next character
        self._typewriter_index += 1
        partial_text = self._typewriter_full_text[:self._typewriter_index]
        self.set_text(partial_text)

        # Call character callback
        if self._on_character_callback and self._typewriter_index > 0:
            char = self._typewriter_full_text[self._typewriter_index - 1]
            self._on_character_callback(char, self._typewriter_index - 1)

    def stop_typewriter(self):
        """Stop ongoing typewriter effect and show full text immediately."""
        self._typewriter_timer.stop()
        if self._typewriter_full_text:
            self.set_text(self._typewriter_full_text)
