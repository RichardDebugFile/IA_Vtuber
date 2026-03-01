"""
conftest.py — Fixtures compartidas para los tests de desktopctl.

Instala los mocks de pynput/pygetwindow/PIL en sys.modules antes de que
cualquier módulo del servicio sea importado. Esto permite correr todos
los tests sin display, mouse ni hardware real.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, call

import pytest
from PIL import Image


# ── Mocks de bajo nivel (instalados una sola vez para toda la sesión) ────────

def _build_mouse_mock():
    mod = types.ModuleType("pynput.mouse")
    controller = MagicMock(name="MouseController")
    controller.position = (0, 0)
    mod.Controller = MagicMock(return_value=controller)
    mod.Button = MagicMock()
    mod.Button.left   = "left"
    mod.Button.right  = "right"
    mod.Button.middle = "middle"
    return mod, controller


def _build_keyboard_mock():
    mod = types.ModuleType("pynput.keyboard")
    controller = MagicMock(name="KeyboardController")
    mod.Controller = MagicMock(return_value=controller)

    key_mock = MagicMock(name="Key")
    for k in (
        "enter", "esc", "tab", "space", "backspace", "delete",
        "up", "down", "left", "right", "home", "end",
        "page_up", "page_down", "ctrl", "shift", "alt", "cmd",
        "caps_lock", "print_screen", "insert", "num_lock", "scroll_lock",
        "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
    ):
        setattr(key_mock, k, f"KEY_{k.upper()}")
    mod.Key = key_mock

    keycode = MagicMock(name="KeyCode")
    keycode.from_char = MagicMock(side_effect=lambda c: f"CHAR_{c}")
    mod.KeyCode = keycode

    ghk_instance = MagicMock(name="GlobalHotKeysInstance")
    ghk_instance.daemon = True
    mod.GlobalHotKeys = MagicMock(return_value=ghk_instance)

    return mod, controller, ghk_instance


def _build_pygetwindow_mock():
    mod = types.ModuleType("pygetwindow")
    mod.getAllWindows = MagicMock(return_value=[])
    return mod


def _build_pil_mock():
    mod = types.ModuleType("PIL.ImageGrab")
    fake_img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
    mod.grab = MagicMock(return_value=fake_img)
    return mod, fake_img


# Construir e instalar mocks
_mouse_mod, _mouse_ctrl    = _build_mouse_mock()
_kb_mod, _kb_ctrl, _ghk    = _build_keyboard_mock()
_pygw_mod                  = _build_pygetwindow_mock()
_imagegrab_mod, _fake_img  = _build_pil_mock()

_pynput_mod = types.ModuleType("pynput")
_pynput_mod.mouse    = _mouse_mod
_pynput_mod.keyboard = _kb_mod

sys.modules.setdefault("pynput",           _pynput_mod)
sys.modules.setdefault("pynput.mouse",     _mouse_mod)
sys.modules.setdefault("pynput.keyboard",  _kb_mod)
sys.modules.setdefault("pygetwindow",      _pygw_mod)
sys.modules.setdefault("PIL.ImageGrab",    _imagegrab_mod)


# ── Importar app DESPUÉS de instalar mocks ───────────────────────────────────

from fastapi.testclient import TestClient  # noqa: E402
from src.server import app                 # noqa: E402
from src import ui_automation as ui        # noqa: E402
from src.hotkeys import hotkey_manager     # noqa: E402


# ── Fixtures públicas ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> TestClient:
    """Cliente FastAPI reutilizable para toda la sesión de tests."""
    return TestClient(app)


@pytest.fixture
def mouse_ctrl():
    """Controlador de mouse mockeado. Se resetea tras cada test."""
    _mouse_ctrl.reset_mock()
    _mouse_ctrl.position = (0, 0)
    return _mouse_ctrl


@pytest.fixture
def kb_ctrl():
    """Controlador de teclado mockeado. Se resetea tras cada test."""
    _kb_ctrl.reset_mock()
    return _kb_ctrl


@pytest.fixture
def pygw():
    """Mock de pygetwindow. Se resetea tras cada test con lista vacía."""
    _pygw_mod.getAllWindows.reset_mock()
    _pygw_mod.getAllWindows.return_value = []
    return _pygw_mod


@pytest.fixture
def imagegrab():
    """Mock de PIL.ImageGrab con imagen fake 1920x1080."""
    _imagegrab_mod.grab.reset_mock()
    _imagegrab_mod.grab.return_value = _fake_img
    return _imagegrab_mod


@pytest.fixture
def fake_window():
    """
    Factoría de ventanas mockeadas.

    Uso:
        def test_foo(fake_window):
            win = fake_window("Notepad", x=0, y=0, w=800, h=600)
    """
    def _make(title: str, x: int = 0, y: int = 0, w: int = 800,
              h: int = 600, minimized: bool = False) -> MagicMock:
        win = MagicMock(name=f"Window({title})")
        win.title      = title
        win.left       = x
        win.top        = y
        win.width      = w
        win.height     = h
        win.isMinimized = minimized
        return win
    return _make


@pytest.fixture
def ghk_instance():
    """Instancia mockeada de GlobalHotKeys."""
    _ghk.reset_mock()
    return _ghk
