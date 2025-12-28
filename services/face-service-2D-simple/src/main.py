from PySide6.QtWidgets import (
    QApplication, QMenu, QWidgetAction, QWidget, QHBoxLayout, QLabel, QSlider
)
from PySide6.QtCore import QTimer, QObject, QEvent, Qt, QPoint
from PySide6.QtGui import QKeySequence, QShortcut
import os, sys

from overlay_window import OverlayWindow
from avatar.avatar_config import load_avatar_cfg
from avatar.avatar_image import AvatarImage
from ui.bubble import TextPanel
from ui.blip_player import BlipPlayer
from ipc.ws_client import WSClient
from ipc.qt_signals import EventBridge   # <--- PUENTE DE SEÑALES
from health_server import start_health_server

GATEWAY_WS = os.getenv("GATEWAY_WS", "ws://127.0.0.1:8765/ws")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8805"))
AVATAR_BASE = os.path.join(os.path.dirname(__file__), "assets", "avatars", "default")

BASE_W, BASE_H = 520, 520  # tamaño base para calcular la escala

def _to_qpoint(p) -> QPoint:
    try:
        return p.toPoint()
    except AttributeError:
        return QPoint(int(p.x()), int(p.y()))

class SceneProxy(QObject):
    """
    - Ctrl + rueda: escala global (redimensiona ventana según BASE_W/H).
    - Clic derecho: menú contextual con slider de escala, presets, 'Cerrar' y 'Expresión'.
    - Arrastrar el avatar: mueve la ventana (nativo).
    - '[' y ']': emoción anterior / siguiente.  Números 1..9: emoción directa.
    """
    def __init__(self, window, avatar_obj, get_scale, set_scale, relayout_cb,
                 get_emotions, get_current_emotion, set_emotion, next_emotion, prev_emotion):
        super().__init__()
        self.window = window
        self.avatar = avatar_obj
        self.get_scale = get_scale
        self.set_scale = set_scale
        self.relayout_cb = relayout_cb
        self.get_emotions = get_emotions
        self.get_current_emotion = get_current_emotion
        self.set_emotion = set_emotion
        self.next_emotion = next_emotion
        self.prev_emotion = prev_emotion

    def eventFilter(self, obj, ev):
        t = ev.type()

        # Zoom global con Ctrl + rueda
        if t == QEvent.GraphicsSceneWheel and (ev.modifiers() & Qt.ControlModifier):
            dy = ev.delta() if hasattr(ev, "delta") else ev.angleDelta().y()
            factor = 1.1 if dy > 0 else (1/1.1)
            self.set_scale(self.get_scale() * factor)
            return True

        # Menú contextual (clic derecho)
        if t == QEvent.GraphicsSceneContextMenu:
            gp = _to_qpoint(ev.screenPos())
            self._show_menu(gp)
            return True

        # Mover ventana arrastrando el avatar
        if t == QEvent.GraphicsSceneMousePress and ev.button() == Qt.LeftButton:
            local = self.avatar.item.mapFromScene(ev.scenePos())
            if self.avatar.item.contains(local):
                self.window.start_native_move()
                return True

        return False

    def _show_menu(self, global_pos: QPoint):
        menu = QMenu()

        # -------- Slider de escala (50% – 300%) --------
        w = QWidget()
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(8)
        lab = QLabel("Escala"); lab.setMinimumWidth(48)
        sld = QSlider(Qt.Horizontal); sld.setRange(50, 300)
        cur = int(round(self.get_scale() * 100))
        sld.setValue(max(50, min(300, cur)))
        val = QLabel(f"{sld.value()}%")
        sld.valueChanged.connect(lambda v: val.setText(f"{v}%"))
        sld.sliderReleased.connect(lambda: self.set_scale(sld.value()/100.0))
        lay.addWidget(lab); lay.addWidget(sld, 1); lay.addWidget(val)
        act_slider = QWidgetAction(menu); act_slider.setDefaultWidget(w)
        menu.addAction(act_slider)

        # -------- Presets --------
        menu.addSeparator()
        for pct in (100, 125, 150, 200):
            a = menu.addAction(f"{pct}%")
            a.triggered.connect(lambda _=False, p=pct: self.set_scale(p/100.0))

        menu.addSeparator()
        menu.addAction("Reset (100%)", lambda: self.set_scale(1.0))

        # -------- Expresión --------
        submenu = QMenu("Expresión", menu)
        current = self.get_current_emotion()
        for i, name in enumerate(self.get_emotions(), start=1):
            label = f"{i}. {name}" if i < 10 else name
            act = submenu.addAction(label)
            if name == current:
                font = act.font(); font.setBold(True); act.setFont(font)
                act.setCheckable(True); act.setChecked(True)
            act.triggered.connect(lambda _=False, n=name: self.set_emotion(n))
        menu.addMenu(submenu)

        # -------- Cerrar --------
        menu.addSeparator()
        menu.addAction("Cerrar…", lambda: self.window.close())

        menu.exec(global_pos)


def main():
    # Start health check server in background
    start_health_server(HEALTH_PORT)

    app = QApplication(sys.argv)

    win = OverlayWindow(width=BASE_W, height=BASE_H, opacity=0.98)

    # Config + avatar
    cfg = load_avatar_cfg(AVATAR_BASE)
    avatar = AvatarImage(win.scene, AVATAR_BASE, cfg)
    avatar.item.setZValue(0)

    # Panel de texto
    panel = TextPanel(
        win.scene,
        max_width=cfg.bubble.max_width,
        font_path=None,
        font_size=cfg.bubble.font_size,
        bg_color=cfg.bubble.color,
        text_color=getattr(cfg.bubble, "text_color", "#1e1e1e"),
        opacity=cfg.bubble.opacity,
    )
    panel.setZValue(1000)
    panel.set_text("Hola, soy tu asistente ✨")

    # -------- Escala de UI (en función de la ventana) --------
    ui_scale = 1.0

    def apply_ui_scale_from_window():
        nonlocal ui_scale
        s = min(win.width()/BASE_W, win.height()/BASE_H)
        s = max(0.5, min(3.0, s))
        ui_scale = s
        avatar.set_scale_factor(s)
        panel.max_width = int(cfg.bubble.max_width * s)
        panel.apply_scale(s)
        relayout()

    def set_ui_scale(new_scale: float):
        s = max(0.5, min(3.0, float(new_scale)))
        w = max(OverlayWindow.MIN_W, int(BASE_W * s))
        h = max(OverlayWindow.MIN_H, int(BASE_H * s))
        win.resize(w, h)  # dispara resized -> apply_ui_scale_from_window()

    def get_ui_scale() -> float:
        return ui_scale

    # -------- Emociones (para test manual) --------
    emotions = list(cfg.emotions.keys()) or ["neutral"]

    def get_current_emotion() -> str:
        try:
            return getattr(avatar, "current_label", "neutral")
        except Exception:
            return "neutral"

    def set_emotion(name: str):
        if name not in emotions:
            return
        avatar.set_emotion(name)
        relayout()

    def _cycle(delta: int):
        cur = get_current_emotion()
        try:
            idx = emotions.index(cur)
        except ValueError:
            idx = 0
        new = emotions[(idx + delta) % len(emotions)]
        set_emotion(new)

    def next_emotion(): _cycle(+1)
    def prev_emotion(): _cycle(-1)

    # -------- Layout del panel respecto al avatar --------
    def relayout():
        mx = int(cfg.bubble.margin.x)
        my = int(cfg.bubble.margin.y)
        ox = int(cfg.bubble.offset.x)
        oy = int(cfg.bubble.offset.y)
        panel.place(cfg.bubble.position, avatar.item, mx, my, ox, oy)

    # Inicial
    apply_ui_scale_from_window()
    win.resized.connect(apply_ui_scale_from_window)

    # Filtro de escena: Ctrl+rueda + menú contextual + drag avatar
    sp = SceneProxy(
        win, avatar,
        get_ui_scale, set_ui_scale, relayout,
        lambda: emotions, get_current_emotion, set_emotion, next_emotion, prev_emotion
    )
    win.scene.installEventFilter(sp)

    # Atajos: escala
    QShortcut(QKeySequence("Ctrl++"), win, activated=lambda: set_ui_scale(get_ui_scale()*1.1))
    QShortcut(QKeySequence("Ctrl+="), win, activated=lambda: set_ui_scale(get_ui_scale()*1.1))
    QShortcut(QKeySequence("Ctrl+-"), win, activated=lambda: set_ui_scale(get_ui_scale()/1.1))
    QShortcut(QKeySequence("Ctrl+0"),  win, activated=lambda: set_ui_scale(1.0))

    # Atajos: emociones
    QShortcut(QKeySequence("]"), win, activated=next_emotion)
    QShortcut(QKeySequence("["), win, activated=prev_emotion)
    for i in range(1, 10):
        QShortcut(QKeySequence(str(i)), win,
                  activated=lambda ix=i: set_emotion(emotions[ix-1]) if ix-1 < len(emotions) else None)

    # --------- PUENTE DE SEÑALES (WS en hilo aparte -> GUI) ---------
    bridge = EventBridge()

    # Blip player para reproducir sonidos sincronizados
    blip_player = BlipPlayer(blips_service_url="http://127.0.0.1:8804")

    # Track current emotion for blips
    current_emotion = {"label": "neutral"}

    def on_emotion_gui(data: dict):
        # recibido en hilo GUI
        emotion = data.get("label", "neutral")
        current_emotion["label"] = emotion
        set_emotion(emotion)

    def on_utterance_gui(data: dict):
        txt = data.get("text", "") or " "

        # Pre-calculate layout based on full text to avoid bubble jumping
        # Set full text temporarily to get proper size, then clear for typewriter
        panel.set_text(txt)
        relayout()

        # Start blip audio playback
        blip_player.play_for_text(txt, current_emotion["label"])

        # Show text with typewriter effect
        # Speed: 50ms per character = 20 characters/second (matches blip speed)
        panel.set_text_typewriter(
            txt,
            speed_ms=50,
            on_character=None,  # Don't relayout on each character
            on_complete=lambda: relayout()  # Final relayout when complete
        )

    bridge.emotion.connect(on_emotion_gui)
    bridge.utterance.connect(on_utterance_gui)

    # WSClient corre en otro hilo → emitimos señales (thread-safe)
    try:
        WSClient(GATEWAY_WS, bridge.emotion.emit, bridge.utterance.emit).start()
    except Exception:
        pass

    # Tick ligero
    t = QTimer(); t.start(33); t.timeout.connect(lambda: None)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
