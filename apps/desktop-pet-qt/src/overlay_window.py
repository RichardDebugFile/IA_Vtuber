from PySide6.QtWidgets import (
    QMainWindow, QGraphicsView, QGraphicsScene, QMessageBox
)
from PySide6.QtCore import Qt, Signal


class OverlayWindow(QMainWindow):
    resized = Signal()

    MIN_W, MIN_H = 280, 280  # útiles si quieres forzar mínimos desde fuera

    def __init__(self, width=520, height=520, opacity=0.98):
        super().__init__()
        self.setWindowTitle("VTuber Overlay")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(opacity)

        # View/Scene (contenedor)
        self.view = QGraphicsView(self)
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setStyleSheet("background: transparent;")
        self.setCentralWidget(self.view)

        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        self.resize(width, height)
        self.scene.setSceneRect(self.view.rect())

        self.show()

    # Mantener la escena sincronizada con la vista
    def resizeEvent(self, e):
        self.scene.setSceneRect(self.view.rect())
        self.resized.emit()
        return super().resizeEvent(e)

    # Permitir mover la ventana (lo llama main al arrastrar el avatar)
    def start_native_move(self):
        handle = self.windowHandle()
        if handle:
            try:
                handle.startSystemMove()
            except Exception:
                pass

    # Confirmación al salir (también se usa si cierras desde el menú)
    def closeEvent(self, e):
        mb = QMessageBox(self)
        mb.setWindowTitle("Salir")
        mb.setText("¿Cerrar la VTuber?")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        e.accept() if mb.exec() == QMessageBox.Yes else e.ignore()
