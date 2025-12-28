from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem
from PySide6.QtCore import QPointF, Qt, QRect
import os

class AvatarImage:
    def __init__(self, scene, base_path:str, cfg):
        self.scene = scene
        self.base = base_path
        self.cfg = cfg
        self.scale_factor = 1.0          # ← zoom en caliente
        self.current_label = "neutral"

        self.item = QGraphicsPixmapItem()
        self.scene.addItem(self.item)

        self.pix = {}  # label -> QPixmap original
        for label, rel in cfg.emotions.items():
            p = QPixmap(os.path.join(self.base, rel))
            if not p.isNull():
                self.pix[label] = p
        if "neutral" not in self.pix and self.pix:
            any_label = next(iter(self.pix))
            self.pix["neutral"] = self.pix[any_label]

        self.set_emotion("neutral")

    # ---- API pública ----
    def set_emotion(self, label:str):
        self.current_label = label or "neutral"
        self._refresh()

    def set_scale_factor(self, f: float):
        # límites razonables
        f = max(0.2, min(3.0, float(f)))
        if abs(f - self.scale_factor) < 1e-6:
            return
        self.scale_factor = f
        self._refresh()

    # ---- internos ----
    def _refresh(self):
        base = self.pix.get(self.current_label) or self.pix.get("neutral")
        if base is None or base.isNull():
            return
        pm = self._resize_pixmap(base)  # aplica size/scale + scale_factor
        self.item.setPixmap(pm)
        self._apply_anchor(pm.width(), pm.height())

    def _resize_pixmap(self, pm: QPixmap) -> QPixmap:
        scfg = getattr(self.cfg, "size", None)
        if scfg:
            # tamaño fijo multiplicado por el zoom
            W = int(scfg.width  * self.scale_factor)
            H = int(scfg.height * self.scale_factor)
            mode = (scfg.mode or "fit").lower()
            if mode == "stretch":
                return pm.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            elif mode == "fill":
                rw = W / pm.width(); rh = H / pm.height()
                s = max(rw, rh)
                sw, sh = int(pm.width()*s), int(pm.height()*s)
                scaled = pm.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = max(0, (sw - W) // 2); y = max(0, (sh - H) // 2)
                return scaled.copy(QRect(x, y, W, H))
            else:  # fit
                return pm.scaled(W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            # scale “base” de config multiplicado por el zoom
            s = float(getattr(self.cfg, "scale", 1.0) or 1.0) * self.scale_factor
            return pm.scaled(int(pm.width()*s), int(pm.height()*s),
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _apply_anchor(self, w:int, h:int):
        sr = self.scene.sceneRect()
        left, right = sr.left(), sr.right()
        top, bottom = sr.top(), sr.bottom()
        a = (self.cfg.anchor or "bottom-right").lower()
        ox, oy = self.cfg.offset.x, self.cfg.offset.y

        if a == "bottom-right":
            x = right - w + ox;                 y = bottom - h + oy
        elif a == "bottom-left":
            x = left + ox;                      y = bottom - h + oy
        elif a == "bottom-center":
            x = (left + right - w)/2 + ox;      y = bottom - h + oy
        elif a == "top-left":
            x = left + ox;                      y = top + oy
        elif a == "top-right":
            x = right - w + ox;                 y = top + oy
        elif a == "top-center":
            x = (left + right - w)/2 + ox;      y = top + oy
        elif a == "center":
            x = (left + right - w)/2 + ox;      y = (top + bottom - h)/2 + oy
        else:
            x = right - w + ox;                 y = bottom - h + oy

        self.item.setOffset(QPointF(0, 0))
        self.item.setPos(x, y)
