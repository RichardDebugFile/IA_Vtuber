"""
server.py — FastAPI del servicio desktopctl (puerto 8807).

Expone control de mouse, teclado, ventanas, captura de pantalla
y hotkeys globales como endpoints REST.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import ui_automation as ui
from src.hotkeys import hotkey_manager

VERSION = "1.0.0"
PORT = int(os.getenv("DESKTOPCTL_PORT", "8807"))


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    hotkey_manager.start()
    print(f"[DESKTOPCTL] v{VERSION} listo en puerto {PORT}")
    yield
    hotkey_manager.stop()
    print("[DESKTOPCTL] Shutdown completo")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="desktopctl",
    version=VERSION,
    description="Control de escritorio: mouse, teclado, ventanas, hotkeys globales.",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ───────────────────────────────────────────────────────────────────

class MouseMoveRequest(BaseModel):
    x: int
    y: int


class MouseClickRequest(BaseModel):
    x: int
    y: int
    button: Literal["left", "right", "middle"] = "left"
    clicks: int = Field(default=1, ge=1, le=10)


class MouseScrollRequest(BaseModel):
    x: int
    y: int
    dy: int = Field(description="Positivo = arriba, negativo = abajo")


class KeyboardTypeRequest(BaseModel):
    text: str = Field(max_length=4096)
    interval: float = Field(default=0.0, ge=0.0, le=1.0,
                            description="Pausa entre caracteres en segundos")


class KeyboardKeyRequest(BaseModel):
    key: str = Field(
        description='Tecla o combinación: "enter", "ctrl+c", "ctrl+shift+s"'
    )


class KeyboardHotkeyRequest(BaseModel):
    keys: list[str] = Field(
        description='Lista de teclas a pulsar simultáneamente: ["ctrl","shift","esc"]'
    )


class WindowPatternRequest(BaseModel):
    title_pattern: str = Field(
        description="Substring (case-insensitive) del título de la ventana"
    )


class HotkeyRegisterRequest(BaseModel):
    combo: str = Field(
        description='Formato pynput: "<ctrl>+<space>", "<ctrl>+z"'
    )
    description: str = ""


class ActionRequest(BaseModel):
    type: Literal[
        "click", "move", "scroll",
        "type", "key", "hotkey",
        "window_focus", "window_minimize", "window_maximize", "window_close",
        "screenshot",
    ]
    # Mouse
    x:       Optional[int] = None
    y:       Optional[int] = None
    button:  Optional[str] = None
    clicks:  Optional[int] = None
    dy:      Optional[int] = None
    # Teclado
    text:    Optional[str] = None
    key:     Optional[str] = None
    keys:    Optional[list[str]] = None
    interval: Optional[float] = None
    # Ventanas / pantalla
    title_pattern: Optional[str] = None
    region:  Optional[list[int]] = None  # [x, y, w, h]


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    screen = ui.get_screen_size()
    return {
        "status":          "ok",
        "service":         "desktopctl",
        "version":         VERSION,
        "screen":          screen,
        "hotkeys_active":  len(hotkey_manager.list_hotkeys()),
    }


# ── Mouse ─────────────────────────────────────────────────────────────────────

@app.post("/mouse/move")
def mouse_move(body: MouseMoveRequest):
    ui.mouse_move(body.x, body.y)
    return {"ok": True, "x": body.x, "y": body.y}


@app.post("/mouse/click")
def mouse_click(body: MouseClickRequest):
    ui.mouse_click(body.x, body.y, body.button, body.clicks)
    return {"ok": True, "x": body.x, "y": body.y, "button": body.button, "clicks": body.clicks}


@app.post("/mouse/scroll")
def mouse_scroll(body: MouseScrollRequest):
    ui.mouse_scroll(body.x, body.y, body.dy)
    return {"ok": True, "x": body.x, "y": body.y, "dy": body.dy}


# ── Teclado ───────────────────────────────────────────────────────────────────

@app.post("/keyboard/type")
def keyboard_type(body: KeyboardTypeRequest):
    ui.keyboard_type(body.text, body.interval)
    return {"ok": True, "chars": len(body.text)}


@app.post("/keyboard/key")
def keyboard_key(body: KeyboardKeyRequest):
    try:
        ui.keyboard_key(body.key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Tecla inválida: {exc}")
    return {"ok": True, "key": body.key}


@app.post("/keyboard/hotkey")
def keyboard_hotkey(body: KeyboardHotkeyRequest):
    if not body.keys:
        raise HTTPException(status_code=400, detail="Se requiere al menos una tecla")
    try:
        ui.keyboard_hotkey(*body.keys)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Combinación inválida: {exc}")
    return {"ok": True, "keys": body.keys}


# ── Ventanas ──────────────────────────────────────────────────────────────────

@app.get("/windows")
def windows():
    return {"windows": ui.list_windows()}


@app.post("/windows/focus")
def window_focus(body: WindowPatternRequest):
    found = ui.focus_window(body.title_pattern)
    if not found:
        raise HTTPException(status_code=404, detail=f"Ventana no encontrada: '{body.title_pattern}'")
    return {"ok": True, "title_pattern": body.title_pattern}


@app.post("/windows/minimize")
def window_minimize(body: WindowPatternRequest):
    found = ui.minimize_window(body.title_pattern)
    if not found:
        raise HTTPException(status_code=404, detail=f"Ventana no encontrada: '{body.title_pattern}'")
    return {"ok": True}


@app.post("/windows/maximize")
def window_maximize(body: WindowPatternRequest):
    found = ui.maximize_window(body.title_pattern)
    if not found:
        raise HTTPException(status_code=404, detail=f"Ventana no encontrada: '{body.title_pattern}'")
    return {"ok": True}


@app.post("/windows/close")
def window_close(body: WindowPatternRequest):
    found = ui.close_window(body.title_pattern)
    if not found:
        raise HTTPException(status_code=404, detail=f"Ventana no encontrada: '{body.title_pattern}'")
    return {"ok": True}


# ── Pantalla ──────────────────────────────────────────────────────────────────

@app.get("/screenshot")
def screenshot(region: Optional[str] = Query(
    default=None,
    description="x,y,w,h — región a capturar. Omitir = pantalla completa."
)):
    parsed_region = None
    if region:
        try:
            parts = [int(v) for v in region.split(",")]
            if len(parts) != 4:
                raise ValueError
            parsed_region = tuple(parts)
        except ValueError:
            raise HTTPException(status_code=400, detail="region debe ser 'x,y,w,h'")

    image_b64 = ui.screenshot(parsed_region)
    return {"image_b64": image_b64, "format": "png"}


@app.get("/screen/size")
def screen_size():
    return ui.get_screen_size()


# ── Hotkeys globales ──────────────────────────────────────────────────────────

@app.get("/hotkeys")
def list_hotkeys():
    return {"hotkeys": hotkey_manager.list_hotkeys()}


@app.post("/hotkeys", status_code=201)
def register_hotkey(body: HotkeyRegisterRequest):
    if not body.combo:
        raise HTTPException(status_code=400, detail="combo no puede estar vacío")

    def _noop():
        pass  # callback vacío — el cliente implementará la lógica

    hotkey_id = hotkey_manager.register(body.combo, _noop, body.description)
    return {"id": hotkey_id, "combo": body.combo}


@app.delete("/hotkeys/{hotkey_id}")
def delete_hotkey(hotkey_id: str):
    removed = hotkey_manager.unregister(hotkey_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Hotkey '{hotkey_id}' no existe o es builtin"
        )
    return {"ok": True, "id": hotkey_id}


# ── Acción compuesta ──────────────────────────────────────────────────────────

@app.post("/action")
def action(body: ActionRequest):
    """
    Endpoint unificado para el LLM: ejecuta una acción en un solo call.

    Elimina la necesidad de que el LLM conozca rutas específicas.
    """
    t = body.type

    try:
        if t == "move":
            _require(body, "x", "y")
            ui.mouse_move(body.x, body.y)
            return {"ok": True, "type": t}

        elif t == "click":
            _require(body, "x", "y")
            ui.mouse_click(body.x, body.y, body.button or "left", body.clicks or 1)
            return {"ok": True, "type": t}

        elif t == "scroll":
            _require(body, "x", "y", "dy")
            ui.mouse_scroll(body.x, body.y, body.dy)
            return {"ok": True, "type": t}

        elif t == "type":
            _require(body, "text")
            ui.keyboard_type(body.text, body.interval or 0.0)
            return {"ok": True, "type": t, "chars": len(body.text)}

        elif t == "key":
            _require(body, "key")
            ui.keyboard_key(body.key)
            return {"ok": True, "type": t}

        elif t == "hotkey":
            _require(body, "keys")
            ui.keyboard_hotkey(*body.keys)
            return {"ok": True, "type": t}

        elif t == "window_focus":
            _require(body, "title_pattern")
            found = ui.focus_window(body.title_pattern)
            return {"ok": found, "type": t}

        elif t == "window_minimize":
            _require(body, "title_pattern")
            found = ui.minimize_window(body.title_pattern)
            return {"ok": found, "type": t}

        elif t == "window_maximize":
            _require(body, "title_pattern")
            found = ui.maximize_window(body.title_pattern)
            return {"ok": found, "type": t}

        elif t == "window_close":
            _require(body, "title_pattern")
            found = ui.close_window(body.title_pattern)
            return {"ok": found, "type": t}

        elif t == "screenshot":
            region = tuple(body.region) if body.region else None
            image_b64 = ui.screenshot(region)
            return {"ok": True, "type": t, "image_b64": image_b64, "format": "png"}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    raise HTTPException(status_code=400, detail=f"Tipo de acción desconocido: {t}")


def _require(body: ActionRequest, *fields: str) -> None:
    missing = [f for f in fields if getattr(body, f, None) is None]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Campos requeridos para este tipo de acción: {missing}"
        )


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=PORT, reload=False)
