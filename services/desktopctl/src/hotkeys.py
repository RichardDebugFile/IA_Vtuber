"""
hotkeys.py — Listener global de teclas de acceso rápido.

Usa pynput.keyboard.GlobalHotKeys en un hilo daemon para que los atajos
funcionen aunque el foco esté en cualquier otra ventana del sistema.

Los hotkeys predefinidos publican eventos al gateway vía HTTP para integrarse
con el bus pub/sub existente (topics: push-to-talk, mute-tts, shutdown).
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx
from pynput import keyboard

logger = logging.getLogger(__name__)

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8800")

# Combos predefinidos cargados desde env (formato pynput: "<ctrl>+<space>")
_DEFAULT_HOTKEYS = {
    "push-to-talk": os.getenv("HOTKEY_PUSH_TO_TALK", "<ctrl>+<space>"),
    "mute-tts":     os.getenv("HOTKEY_MUTE_TTS",     "<ctrl>+<shift>+m"),
    "shutdown":     os.getenv("HOTKEY_SHUTDOWN",     "<ctrl>+<shift>+q"),
}


@dataclass
class HotkeyEntry:
    id: str
    combo: str
    description: str
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    builtin: bool = False


class HotkeyManager:
    """
    Gestiona hotkeys globales con pynput.GlobalHotKeys.

    Ciclo de vida:
        manager = HotkeyManager()
        manager.start()         # lanza el listener en hilo daemon
        manager.register(...)   # añade hotkeys en caliente
        manager.stop()          # detiene el listener
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, HotkeyEntry] = {}          # id → entry
        self._callbacks: dict[str, Callable] = {}           # combo → callback
        self._listener: keyboard.GlobalHotKeys | None = None
        self._thread: threading.Thread | None = None

    # ── API pública ──────────────────────────────────────────────────────────

    def register(
        self,
        combo: str,
        callback: Callable,
        description: str = "",
        builtin: bool = False,
    ) -> str:
        """
        Registra un hotkey global.

        Args:
            combo:       Formato pynput, p.ej. "<ctrl>+<space>" o "<ctrl>+z".
            callback:    Función sin argumentos llamada cuando se detecte el combo.
            description: Texto descriptivo para la API.
            builtin:     True = cargado en startup, no se puede eliminar por API.

        Returns:
            ID único del hotkey registrado.
        """
        hotkey_id = str(uuid.uuid4())[:8]
        entry = HotkeyEntry(
            id=hotkey_id,
            combo=combo,
            description=description,
            builtin=builtin,
        )
        with self._lock:
            self._entries[hotkey_id] = entry
            self._callbacks[combo] = callback
            self._restart_listener()

        logger.info("[HOTKEYS] Registrado %s → %s", combo, description or hotkey_id)
        return hotkey_id

    def unregister(self, hotkey_id: str) -> bool:
        """
        Elimina un hotkey por ID.

        Returns:
            True si se eliminó, False si no existía o era builtin.
        """
        with self._lock:
            entry = self._entries.get(hotkey_id)
            if entry is None:
                return False
            if entry.builtin:
                logger.warning("[HOTKEYS] No se puede eliminar hotkey builtin: %s", hotkey_id)
                return False
            del self._entries[hotkey_id]
            self._callbacks.pop(entry.combo, None)
            self._restart_listener()

        logger.info("[HOTKEYS] Eliminado %s (%s)", hotkey_id, entry.combo)
        return True

    def list_hotkeys(self) -> list[dict]:
        """Devuelve todos los hotkeys registrados."""
        with self._lock:
            return [
                {
                    "id":            e.id,
                    "combo":         e.combo,
                    "description":   e.description,
                    "registered_at": e.registered_at,
                    "builtin":       e.builtin,
                }
                for e in self._entries.values()
            ]

    def start(self) -> None:
        """Registra los hotkeys predefinidos y lanza el listener."""
        self._register_builtins()
        self._restart_listener()
        logger.info("[HOTKEYS] Manager iniciado con %d hotkeys", len(self._entries))

    def stop(self) -> None:
        """Detiene el listener."""
        with self._lock:
            if self._listener:
                self._listener.stop()
                self._listener = None
        logger.info("[HOTKEYS] Manager detenido")

    # ── Interno ──────────────────────────────────────────────────────────────

    def _restart_listener(self) -> None:
        """Para el listener actual y lo relanza con los callbacks actuales."""
        if self._listener:
            self._listener.stop()
            self._listener = None

        if not self._callbacks:
            return

        # GlobalHotKeys requiere dict {combo: callback}
        self._listener = keyboard.GlobalHotKeys(dict(self._callbacks))
        self._listener.daemon = True
        self._listener.start()

    def _register_builtins(self) -> None:
        """Registra los hotkeys predefinidos desde variables de entorno."""
        self.register(
            combo=_DEFAULT_HOTKEYS["push-to-talk"],
            callback=lambda: self._publish_event("push-to-talk", {}),
            description="Activar/desactivar STT (push-to-talk)",
            builtin=True,
        )
        self.register(
            combo=_DEFAULT_HOTKEYS["mute-tts"],
            callback=lambda: self._publish_event("mute-tts", {}),
            description="Silenciar/reanudar TTS",
            builtin=True,
        )
        self.register(
            combo=_DEFAULT_HOTKEYS["shutdown"],
            callback=lambda: self._publish_event("shutdown", {}),
            description="Apagar todos los servicios",
            builtin=True,
        )

    @staticmethod
    def _publish_event(topic: str, data: dict) -> None:
        """Publica un evento en el bus pub/sub del gateway (fire-and-forget)."""
        try:
            httpx.post(
                f"{GATEWAY_URL}/publish",
                json={"topic": topic, "data": data},
                timeout=2.0,
            )
            logger.debug("[HOTKEYS] Evento publicado: %s", topic)
        except Exception as exc:
            logger.warning("[HOTKEYS] No se pudo publicar '%s': %s", topic, exc)


# Instancia global — importada por server.py
hotkey_manager = HotkeyManager()
