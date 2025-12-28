# apps/desktop-pet-qt/src/ipc/qt_signals.py
from PySide6.QtCore import QObject, Signal

class EventBridge(QObject):
    """
    Puente de señales Qt para cruzar hilos.
    Puedes emitir estas señales desde cualquier hilo;
    Qt las entregará en el hilo del receptor (la GUI).
    """
    emotion = Signal(dict)    # {"label": "happy"}
    utterance = Signal(dict)  # {"text": "Hola!"}
