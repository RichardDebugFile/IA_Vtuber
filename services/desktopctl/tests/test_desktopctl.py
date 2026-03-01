"""
Tests offline de desktopctl.

No requieren servicios activos, display ni hardware real.
pynput, pygetwindow y PIL.ImageGrab se mockean completamente.
"""
from __future__ import annotations

import base64
import io
import sys
import types
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from fastapi.testclient import TestClient


# ── Mocks de dependencias nativas ────────────────────────────────────────────
# Se deben aplicar ANTES de importar cualquier módulo del servicio.

def _make_pynput_mock():
    """Crea un mock completo del módulo pynput."""
    pynput_mod = types.ModuleType("pynput")

    # pynput.mouse
    mouse_mod = types.ModuleType("pynput.mouse")
    mouse_mod.Controller = MagicMock()
    mouse_mod.Button = MagicMock()
    mouse_mod.Button.left = "left"
    mouse_mod.Button.right = "right"
    mouse_mod.Button.middle = "middle"
    pynput_mod.mouse = mouse_mod

    # pynput.keyboard
    kb_mod = types.ModuleType("pynput.keyboard")
    kb_mod.Controller = MagicMock()
    kb_mod.Key = MagicMock()
    kb_mod.KeyCode = MagicMock()
    kb_mod.KeyCode.from_char = MagicMock(side_effect=lambda c: c)

    # GlobalHotKeys: instancia con daemon=True, start(), stop()
    ghk_instance = MagicMock()
    ghk_instance.daemon = True
    kb_mod.GlobalHotKeys = MagicMock(return_value=ghk_instance)

    pynput_mod.keyboard = kb_mod

    return pynput_mod, mouse_mod, kb_mod


def _make_pygetwindow_mock():
    win_mod = types.ModuleType("pygetwindow")
    win_mod.getAllWindows = MagicMock(return_value=[])
    return win_mod


def _make_pil_mock():
    pil_mod = types.ModuleType("PIL")
    imagegrab_mod = types.ModuleType("PIL.ImageGrab")

    # Imagen fake 100x100 blanca
    from PIL import Image  # PIL real para crear imagen de prueba
    fake_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    imagegrab_mod.grab = MagicMock(return_value=fake_img)
    pil_mod.ImageGrab = imagegrab_mod

    return pil_mod, imagegrab_mod


# Instalar mocks en sys.modules
_pynput, _pynput_mouse, _pynput_kb = _make_pynput_mock()
_pygw = _make_pygetwindow_mock()
_pil, _imagegrab = _make_pil_mock()

sys.modules.setdefault("pynput",           _pynput)
sys.modules.setdefault("pynput.mouse",     _pynput_mouse)
sys.modules.setdefault("pynput.keyboard",  _pynput_kb)
sys.modules.setdefault("pygetwindow",      _pygw)
sys.modules.setdefault("PIL.ImageGrab",    _imagegrab)

# Ahora sí se puede importar
from src.server import app  # noqa: E402

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_window(title: str, x=0, y=0, w=800, h=600, minimized=False):
    win = MagicMock()
    win.title = title
    win.left, win.top = x, y
    win.width, win.height = w, h
    win.isMinimized = minimized
    return win


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "desktopctl"
    assert "version" in data
    assert "screen" in data
    assert "hotkeys_active" in data


# ── Mouse ─────────────────────────────────────────────────────────────────────

def test_mouse_move():
    with patch("src.ui_automation.mouse_move") as mock_move:
        r = client.post("/mouse/move", json={"x": 100, "y": 200})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_move.assert_called_once_with(100, 200)


def test_mouse_click_default_button():
    with patch("src.ui_automation.mouse_click") as mock_click:
        r = client.post("/mouse/click", json={"x": 50, "y": 75})
    assert r.status_code == 200
    mock_click.assert_called_once_with(50, 75, "left", 1)


def test_mouse_click_right_double():
    with patch("src.ui_automation.mouse_click") as mock_click:
        r = client.post("/mouse/click", json={"x": 10, "y": 20, "button": "right", "clicks": 2})
    assert r.status_code == 200
    mock_click.assert_called_once_with(10, 20, "right", 2)


def test_mouse_scroll():
    with patch("src.ui_automation.mouse_scroll") as mock_scroll:
        r = client.post("/mouse/scroll", json={"x": 0, "y": 0, "dy": -3})
    assert r.status_code == 200
    mock_scroll.assert_called_once_with(0, 0, -3)


# ── Teclado ───────────────────────────────────────────────────────────────────

def test_keyboard_type():
    with patch("src.ui_automation.keyboard_type") as mock_type:
        r = client.post("/keyboard/type", json={"text": "Hola mundo"})
    assert r.status_code == 200
    assert r.json()["chars"] == 10
    mock_type.assert_called_once_with("Hola mundo", 0.0)


def test_keyboard_type_with_interval():
    with patch("src.ui_automation.keyboard_type") as mock_type:
        r = client.post("/keyboard/type", json={"text": "abc", "interval": 0.05})
    assert r.status_code == 200
    mock_type.assert_called_once_with("abc", 0.05)


def test_keyboard_key_enter():
    with patch("src.ui_automation.keyboard_key") as mock_key:
        r = client.post("/keyboard/key", json={"key": "enter"})
    assert r.status_code == 200
    mock_key.assert_called_once_with("enter")


def test_keyboard_key_combination():
    with patch("src.ui_automation.keyboard_key") as mock_key:
        r = client.post("/keyboard/key", json={"key": "ctrl+z"})
    assert r.status_code == 200
    mock_key.assert_called_once_with("ctrl+z")


def test_keyboard_hotkey():
    with patch("src.ui_automation.keyboard_hotkey") as mock_hk:
        r = client.post("/keyboard/hotkey", json={"keys": ["ctrl", "shift", "esc"]})
    assert r.status_code == 200
    mock_hk.assert_called_once_with("ctrl", "shift", "esc")


def test_keyboard_hotkey_empty_list_returns_400():
    r = client.post("/keyboard/hotkey", json={"keys": []})
    assert r.status_code == 400


# ── Ventanas ──────────────────────────────────────────────────────────────────

def test_list_windows_empty():
    _pygw.getAllWindows.return_value = []
    r = client.get("/windows")
    assert r.status_code == 200
    assert r.json()["windows"] == []


def test_list_windows_filters_empty_titles():
    _pygw.getAllWindows.return_value = [
        _fake_window("Notepad"),
        _fake_window(""),           # debe filtrarse
        _fake_window("VS Code"),
    ]
    r = client.get("/windows")
    assert r.status_code == 200
    titles = [w["title"] for w in r.json()["windows"]]
    assert "Notepad" in titles
    assert "VS Code" in titles
    assert "" not in titles


def test_window_focus_found():
    win = _fake_window("Notepad")
    _pygw.getAllWindows.return_value = [win]
    r = client.post("/windows/focus", json={"title_pattern": "notepad"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    win.activate.assert_called_once()


def test_window_focus_not_found():
    _pygw.getAllWindows.return_value = []
    r = client.post("/windows/focus", json={"title_pattern": "NoExiste"})
    assert r.status_code == 404


def test_window_minimize():
    win = _fake_window("Chrome")
    _pygw.getAllWindows.return_value = [win]
    r = client.post("/windows/minimize", json={"title_pattern": "Chrome"})
    assert r.status_code == 200
    win.minimize.assert_called_once()


def test_window_maximize():
    win = _fake_window("Chrome")
    _pygw.getAllWindows.return_value = [win]
    r = client.post("/windows/maximize", json={"title_pattern": "Chrome"})
    assert r.status_code == 200
    win.maximize.assert_called_once()


def test_window_close():
    win = _fake_window("Bloc de notas")
    _pygw.getAllWindows.return_value = [win]
    r = client.post("/windows/close", json={"title_pattern": "Bloc"})
    assert r.status_code == 200
    win.close.assert_called_once()


# ── Pantalla ──────────────────────────────────────────────────────────────────

def test_screenshot_full():
    r = client.get("/screenshot")
    assert r.status_code == 200
    data = r.json()
    assert data["format"] == "png"
    # Verificar que es base64 válido
    decoded = base64.b64decode(data["image_b64"])
    assert len(decoded) > 0


def test_screenshot_region():
    r = client.get("/screenshot?region=10,20,200,100")
    assert r.status_code == 200
    assert r.json()["format"] == "png"


def test_screenshot_region_invalid():
    r = client.get("/screenshot?region=10,20")  # solo 2 valores
    assert r.status_code == 400


def test_screen_size():
    r = client.get("/screen/size")
    assert r.status_code == 200
    data = r.json()
    assert "width" in data
    assert "height" in data
    assert data["width"] == 100   # tamaño de la imagen fake
    assert data["height"] == 100


# ── Hotkeys API ───────────────────────────────────────────────────────────────

def test_list_hotkeys_returns_builtins():
    r = client.get("/hotkeys")
    assert r.status_code == 200
    hotkeys = r.json()["hotkeys"]
    # Los 3 builtins deben estar registrados en startup
    assert len(hotkeys) >= 3
    combos = [h["combo"] for h in hotkeys]
    assert any("ctrl" in c for c in combos)


def test_register_hotkey():
    r = client.post("/hotkeys", json={"combo": "<ctrl>+<alt>+t", "description": "Test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["combo"] == "<ctrl>+<alt>+t"


def test_delete_hotkey_not_found():
    r = client.delete("/hotkeys/nonexistent")
    assert r.status_code == 404


def test_delete_builtin_hotkey_rejected():
    # Obtener ID de un hotkey builtin
    hotkeys = client.get("/hotkeys").json()["hotkeys"]
    builtin = next((h for h in hotkeys if h.get("builtin")), None)
    if builtin:
        r = client.delete(f"/hotkeys/{builtin['id']}")
        assert r.status_code == 404  # builtins no se pueden eliminar


def test_register_and_delete_hotkey():
    r = client.post("/hotkeys", json={"combo": "<ctrl>+<alt>+x", "description": "Temporal"})
    assert r.status_code == 201
    hotkey_id = r.json()["id"]

    r2 = client.delete(f"/hotkeys/{hotkey_id}")
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


# ── Acción compuesta ──────────────────────────────────────────────────────────

def test_action_click():
    with patch("src.ui_automation.mouse_click") as mock_click:
        r = client.post("/action", json={"type": "click", "x": 50, "y": 100})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_click.assert_called_once()


def test_action_type():
    with patch("src.ui_automation.keyboard_type") as mock_type:
        r = client.post("/action", json={"type": "type", "text": "test"})
    assert r.status_code == 200
    mock_type.assert_called_once()


def test_action_screenshot():
    r = client.post("/action", json={"type": "screenshot"})
    assert r.status_code == 200
    assert "image_b64" in r.json()


def test_action_window_focus_not_found():
    _pygw.getAllWindows.return_value = []
    r = client.post("/action", json={"type": "window_focus", "title_pattern": "NoExiste"})
    assert r.status_code == 200
    assert r.json()["ok"] is False  # no lanza 404, devuelve ok=False


def test_action_missing_required_field():
    # click sin x e y
    r = client.post("/action", json={"type": "click"})
    assert r.status_code == 422


def test_action_key():
    with patch("src.ui_automation.keyboard_key") as mock_key:
        r = client.post("/action", json={"type": "key", "key": "enter"})
    assert r.status_code == 200
    mock_key.assert_called_once_with("enter")


def test_action_hotkey():
    with patch("src.ui_automation.keyboard_hotkey") as mock_hk:
        r = client.post("/action", json={"type": "hotkey", "keys": ["ctrl", "a"]})
    assert r.status_code == 200
    mock_hk.assert_called_once_with("ctrl", "a")
