"""
ui_automation.py — Wrapper puro sobre pynput y pygetwindow.

Sin dependencias HTTP. Importable y testeable de forma aislada
mockeando pynput/pygetwindow/PIL.
"""
from __future__ import annotations

import base64
import io
import re
import time
from typing import Any

import pygetwindow as gw
from PIL import ImageGrab
from pynput import keyboard, mouse

# ── Mouse ────────────────────────────────────────────────────────────────────

_MOUSE = mouse.Controller()

_BUTTON_MAP = {
    "left":   mouse.Button.left,
    "right":  mouse.Button.right,
    "middle": mouse.Button.middle,
}


def mouse_move(x: int, y: int) -> None:
    """Mueve el cursor a la posición absoluta (x, y)."""
    _MOUSE.position = (x, y)


def mouse_click(
    x: int, y: int, button: str = "left", clicks: int = 1
) -> None:
    """
    Mueve el cursor a (x, y) y hace click.

    Args:
        x, y:    Coordenadas absolutas en pantalla.
        button:  "left" | "right" | "middle"
        clicks:  Número de clicks (2 = doble click).
    """
    btn = _BUTTON_MAP.get(button, mouse.Button.left)
    _MOUSE.position = (x, y)
    _MOUSE.click(btn, clicks)


def mouse_scroll(x: int, y: int, dy: int) -> None:
    """
    Mueve el cursor a (x, y) y hace scroll vertical.

    Args:
        dy: Positivo = arriba, negativo = abajo.
    """
    _MOUSE.position = (x, y)
    _MOUSE.scroll(0, dy)


# ── Teclado ──────────────────────────────────────────────────────────────────

_KB = keyboard.Controller()

# Teclas especiales reconocidas por nombre de string
_KEY_MAP: dict[str, keyboard.Key] = {
    "enter":      keyboard.Key.enter,
    "return":     keyboard.Key.enter,
    "esc":        keyboard.Key.esc,
    "escape":     keyboard.Key.esc,
    "tab":        keyboard.Key.tab,
    "space":      keyboard.Key.space,
    "backspace":  keyboard.Key.backspace,
    "delete":     keyboard.Key.delete,
    "del":        keyboard.Key.delete,
    "up":         keyboard.Key.up,
    "down":       keyboard.Key.down,
    "left":       keyboard.Key.left,
    "right":      keyboard.Key.right,
    "home":       keyboard.Key.home,
    "end":        keyboard.Key.end,
    "page_up":    keyboard.Key.page_up,
    "page_down":  keyboard.Key.page_down,
    "f1":  keyboard.Key.f1,  "f2":  keyboard.Key.f2,
    "f3":  keyboard.Key.f3,  "f4":  keyboard.Key.f4,
    "f5":  keyboard.Key.f5,  "f6":  keyboard.Key.f6,
    "f7":  keyboard.Key.f7,  "f8":  keyboard.Key.f8,
    "f9":  keyboard.Key.f9,  "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
    "ctrl":  keyboard.Key.ctrl,  "control": keyboard.Key.ctrl,
    "shift": keyboard.Key.shift,
    "alt":   keyboard.Key.alt,
    "win":   keyboard.Key.cmd,  "cmd": keyboard.Key.cmd,
    "caps_lock": keyboard.Key.caps_lock,
    "print_screen": keyboard.Key.print_screen,
    "insert": keyboard.Key.insert,
    "num_lock": keyboard.Key.num_lock,
    "scroll_lock": keyboard.Key.scroll_lock,
}


def _resolve_key(key_str: str) -> keyboard.Key | keyboard.KeyCode:
    """Convierte un string como 'enter', 'ctrl', 'a' en objeto pynput."""
    normalized = key_str.strip().lower()
    if normalized in _KEY_MAP:
        return _KEY_MAP[normalized]
    # Carácter individual
    return keyboard.KeyCode.from_char(key_str)


def keyboard_type(text: str, interval: float = 0.0) -> None:
    """
    Escribe texto carácter a carácter.

    Args:
        text:     Texto a escribir.
        interval: Pausa en segundos entre cada carácter (0.0 = máxima velocidad).
    """
    if interval > 0:
        for char in text:
            _KB.press(char)
            _KB.release(char)
            time.sleep(interval)
    else:
        _KB.type(text)


def keyboard_key(key: str) -> None:
    """
    Pulsa y suelta una tecla especial o combinación tipo 'ctrl+c'.

    Ejemplos:
        keyboard_key("enter")
        keyboard_key("ctrl+z")
        keyboard_key("ctrl+shift+s")
    """
    parts = [p.strip() for p in key.split("+")]
    keys = [_resolve_key(p) for p in parts]

    if len(keys) == 1:
        _KB.press(keys[0])
        _KB.release(keys[0])
    else:
        # Pulsar modificadores primero, soltar en orden inverso
        for k in keys[:-1]:
            _KB.press(k)
        _KB.press(keys[-1])
        _KB.release(keys[-1])
        for k in reversed(keys[:-1]):
            _KB.release(k)


def keyboard_hotkey(*keys: str) -> None:
    """
    Pulsa varias teclas simultáneamente (como keyboard_key pero aceptando lista).

    Ejemplo:
        keyboard_hotkey("ctrl", "shift", "esc")
    """
    keyboard_key("+".join(keys))


# ── Ventanas ─────────────────────────────────────────────────────────────────

def list_windows() -> list[dict[str, Any]]:
    """
    Devuelve lista de ventanas visibles con título no vacío.

    Returns:
        [{title, x, y, width, height, minimized}]
    """
    result = []
    for w in gw.getAllWindows():
        if not w.title:
            continue
        result.append({
            "title":     w.title,
            "x":         w.left,
            "y":         w.top,
            "width":     w.width,
            "height":    w.height,
            "minimized": w.isMinimized,
        })
    return result


def _find_window(title_pattern: str) -> Any | None:
    """Busca la primera ventana cuyo título contenga title_pattern (case-insensitive)."""
    pattern = re.compile(re.escape(title_pattern), re.IGNORECASE)
    for w in gw.getAllWindows():
        if w.title and pattern.search(w.title):
            return w
    return None


def focus_window(title_pattern: str) -> bool:
    """Trae al frente la primera ventana que coincida con title_pattern."""
    w = _find_window(title_pattern)
    if w is None:
        return False
    if w.isMinimized:
        w.restore()
    w.activate()
    return True


def minimize_window(title_pattern: str) -> bool:
    """Minimiza la primera ventana que coincida."""
    w = _find_window(title_pattern)
    if w is None:
        return False
    w.minimize()
    return True


def maximize_window(title_pattern: str) -> bool:
    """Maximiza la primera ventana que coincida."""
    w = _find_window(title_pattern)
    if w is None:
        return False
    w.maximize()
    return True


def close_window(title_pattern: str) -> bool:
    """Cierra la primera ventana que coincida."""
    w = _find_window(title_pattern)
    if w is None:
        return False
    w.close()
    return True


# ── Pantalla ─────────────────────────────────────────────────────────────────

def screenshot(region: tuple[int, int, int, int] | None = None) -> str:
    """
    Captura la pantalla y devuelve imagen en base64 PNG.

    Args:
        region: (x, y, width, height) — None = pantalla completa.

    Returns:
        String base64 de la imagen PNG.
    """
    if region is not None:
        x, y, w, h = region
        bbox = (x, y, x + w, y + h)
    else:
        bbox = None

    img = ImageGrab.grab(bbox=bbox)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def get_screen_size() -> dict[str, int]:
    """Devuelve la resolución del monitor principal."""
    img = ImageGrab.grab()
    return {"width": img.width, "height": img.height}
