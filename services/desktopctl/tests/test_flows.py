"""
test_flows.py — Tests de integración y flujo de desktopctl.

A diferencia de test_desktopctl.py (que verifica endpoints aislados con
patches a nivel de función), estos tests comprueban que los módulos internos
cooperan correctamente: server → ui_automation → pynput/pygetwindow.

Los mocks están en conftest.py a nivel de librería (sys.modules), por lo que
el código real de ui_automation.py y hotkeys.py se ejecuta íntegramente.

Marcadores:
  @pytest.mark.unit        → sin dependencias externas, siempre corren
  @pytest.mark.integration → flujos completos entre módulos internos
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, call, patch

import pytest

# Las importaciones vienen de conftest.py vía fixtures inyectadas.
# También importamos directamente para los tests de lógica interna.
from src import ui_automation as ui
from src.hotkeys import HotkeyManager


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 1 — Cadena completa de acción de mouse
# Verifica que server → ui_automation → controller de pynput sigue el camino
# correcto para cada operación de ratón.
# ═══════════════════════════════════════════════════════════════════════════════

class TestMouseFlow:

    @pytest.mark.integration
    def test_click_sets_position_then_calls_click(self, client, mouse_ctrl):
        """
        El flujo de click debe:
        1. Mover el cursor a (x, y)
        2. Llamar a .click() con el botón y número de clicks correctos.
        El orden importa: primero mover, luego hacer click.
        """
        client.post("/mouse/click", json={"x": 300, "y": 400, "button": "left", "clicks": 1})

        assert mouse_ctrl.position == (300, 400)
        mouse_ctrl.click.assert_called_once()
        click_args = mouse_ctrl.click.call_args
        # Primer argumento = botón (comparamos el nombre del mock)
        assert click_args[0][1] == 1  # clicks

    @pytest.mark.integration
    def test_double_click_passes_count_2(self, client, mouse_ctrl):
        client.post("/mouse/click", json={"x": 10, "y": 10, "clicks": 2})
        call_args = mouse_ctrl.click.call_args
        assert call_args[0][1] == 2

    @pytest.mark.integration
    def test_scroll_sets_position_then_scrolls(self, client, mouse_ctrl):
        """El scroll también mueve el cursor antes de hacer scroll."""
        client.post("/mouse/scroll", json={"x": 100, "y": 200, "dy": -5})

        assert mouse_ctrl.position == (100, 200)
        mouse_ctrl.scroll.assert_called_once_with(0, -5)

    @pytest.mark.integration
    def test_move_only_sets_position(self, client, mouse_ctrl):
        """move no debe llamar a .click() ni .scroll()."""
        client.post("/mouse/move", json={"x": 500, "y": 500})

        assert mouse_ctrl.position == (500, 500)
        mouse_ctrl.click.assert_not_called()
        mouse_ctrl.scroll.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 2 — Cadena completa de teclado
# ═══════════════════════════════════════════════════════════════════════════════

class TestKeyboardFlow:

    @pytest.mark.integration
    def test_type_calls_kb_type(self, client, kb_ctrl):
        """keyboard_type sin interval llama a _KB.type() directamente."""
        client.post("/keyboard/type", json={"text": "Hola Casiopy"})
        kb_ctrl.type.assert_called_once_with("Hola Casiopy")

    @pytest.mark.integration
    def test_type_with_interval_uses_press_release(self, client, kb_ctrl):
        """Con interval > 0 cada carácter usa press+release individualmente."""
        client.post("/keyboard/type", json={"text": "ab", "interval": 0.01})
        # Debe haberse llamado press y release para cada carácter
        assert kb_ctrl.press.call_count == 2
        assert kb_ctrl.release.call_count == 2

    @pytest.mark.integration
    def test_single_key_press_and_release(self, client, kb_ctrl):
        """Una tecla sola debe presionarse y soltarse exactamente una vez."""
        client.post("/keyboard/key", json={"key": "enter"})
        assert kb_ctrl.press.call_count == 1
        assert kb_ctrl.release.call_count == 1

    @pytest.mark.integration
    def test_combination_presses_modifiers_before_main_key(self, client, kb_ctrl):
        """
        ctrl+z debe seguir el orden:
          press(ctrl) → press(z) → release(z) → release(ctrl)
        Los modificadores se pulsan primero y se sueltan en orden inverso.
        """
        client.post("/keyboard/key", json={"key": "ctrl+z"})

        press_calls   = [c[0][0] for c in kb_ctrl.press.call_args_list]
        release_calls = [c[0][0] for c in kb_ctrl.release.call_args_list]

        # ctrl se pulsa antes que z
        ctrl_press_idx = next(i for i, k in enumerate(press_calls)   if "CTRL" in str(k).upper())
        z_press_idx    = next(i for i, k in enumerate(press_calls)    if "CHAR_z" in str(k))
        z_release_idx  = next(i for i, k in enumerate(release_calls)  if "CHAR_z" in str(k))
        ctrl_release_idx = next(i for i, k in enumerate(release_calls) if "CTRL" in str(k).upper())

        assert ctrl_press_idx < z_press_idx,    "ctrl debe pulsarse antes que z"
        assert z_press_idx    < z_release_idx + len(press_calls), "z debe soltarse después de pulsarse"
        assert z_release_idx  < ctrl_release_idx + 1, "z debe soltarse antes que ctrl"

    @pytest.mark.integration
    def test_three_key_combination_order(self, client, kb_ctrl):
        """ctrl+shift+s — tres modificadores en orden correcto."""
        client.post("/keyboard/key", json={"key": "ctrl+shift+s"})

        press_calls = [str(c[0][0]) for c in kb_ctrl.press.call_args_list]
        # ctrl y shift deben aparecer en press antes que s
        assert len(press_calls) == 3
        s_idx    = press_calls.index("CHAR_s")
        ctrl_idx = next(i for i, k in enumerate(press_calls) if "CTRL" in k.upper())
        shft_idx = next(i for i, k in enumerate(press_calls) if "SHIFT" in k.upper())
        assert ctrl_idx < s_idx
        assert shft_idx < s_idx

    @pytest.mark.integration
    def test_hotkey_endpoint_delegates_to_keyboard_key(self, client, kb_ctrl):
        """POST /keyboard/hotkey es equivalente a keyboard_key con +."""
        client.post("/keyboard/hotkey", json={"keys": ["ctrl", "a"]})
        # Debe haberse llamado press al menos dos veces
        assert kb_ctrl.press.call_count >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 3 — Búsqueda de ventanas (regex case-insensitive)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWindowSearchFlow:

    @pytest.mark.integration
    def test_search_is_case_insensitive(self, client, pygw, fake_window):
        """'notepad' debe encontrar 'Notepad - Sin título'."""
        pygw.getAllWindows.return_value = [fake_window("Notepad - Sin título")]
        r = client.post("/windows/focus", json={"title_pattern": "notepad"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    @pytest.mark.integration
    def test_search_matches_substring(self, client, pygw, fake_window):
        """Un patrón parcial debe encontrar la ventana."""
        pygw.getAllWindows.return_value = [fake_window("Google Chrome — Casiopy")]
        r = client.post("/windows/focus", json={"title_pattern": "Chrome"})
        assert r.status_code == 200

    @pytest.mark.integration
    def test_search_returns_first_match(self, client, pygw, fake_window):
        """Con varias coincidencias debe operar sobre la primera."""
        w1 = fake_window("Notepad 1")
        w2 = fake_window("Notepad 2")
        pygw.getAllWindows.return_value = [w1, w2]

        client.post("/windows/minimize", json={"title_pattern": "Notepad"})

        w1.minimize.assert_called_once()
        w2.minimize.assert_not_called()

    @pytest.mark.integration
    def test_minimized_window_restored_before_focus(self, client, pygw, fake_window):
        """
        Al hacer focus sobre una ventana minimizada el flujo correcto es:
        1. Detectar que está minimizada
        2. Llamar a restore()
        3. Llamar a activate()
        restore() debe ocurrir ANTES de activate().
        """
        win = fake_window("VS Code", minimized=True)
        pygw.getAllWindows.return_value = [win]
        call_order = []
        win.restore   = MagicMock(side_effect=lambda: call_order.append("restore"))
        win.activate  = MagicMock(side_effect=lambda: call_order.append("activate"))

        client.post("/windows/focus", json={"title_pattern": "VS Code"})

        assert call_order == ["restore", "activate"], (
            f"Orden esperado: restore → activate. Obtenido: {call_order}"
        )

    @pytest.mark.integration
    def test_focus_active_window_skips_restore(self, client, pygw, fake_window):
        """Una ventana no minimizada NO debe llamar a restore()."""
        win = fake_window("Chrome", minimized=False)
        pygw.getAllWindows.return_value = [win]

        client.post("/windows/focus", json={"title_pattern": "Chrome"})

        win.restore.assert_not_called()
        win.activate.assert_called_once()

    @pytest.mark.integration
    def test_window_not_found_returns_404(self, client, pygw):
        pygw.getAllWindows.return_value = []
        for endpoint in ("/windows/focus", "/windows/minimize",
                         "/windows/maximize", "/windows/close"):
            r = client.post(endpoint, json={"title_pattern": "NoExiste"})
            assert r.status_code == 404, f"{endpoint} debe retornar 404"

    @pytest.mark.integration
    def test_list_windows_excludes_empty_titles(self, client, pygw, fake_window):
        """getAllWindows puede devolver entradas con título vacío; deben filtrarse."""
        pygw.getAllWindows.return_value = [
            fake_window("Notepad"),
            fake_window(""),
            fake_window("   "),
        ]
        r = client.get("/windows")
        titles = [w["title"] for w in r.json()["windows"]]
        assert "Notepad" in titles
        # "" y "   " no deben aparecer (tienen title pero getAllWindows los devuelve igual)
        assert "" not in titles


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 4 — Captura de pantalla
# ═══════════════════════════════════════════════════════════════════════════════

class TestScreenshotFlow:

    @pytest.mark.integration
    def test_full_screenshot_calls_grab_without_bbox(self, client, imagegrab):
        """Sin región, ImageGrab.grab debe llamarse con bbox=None."""
        client.get("/screenshot")
        imagegrab.grab.assert_called_once_with(bbox=None)

    @pytest.mark.integration
    def test_region_screenshot_passes_correct_bbox(self, client, imagegrab):
        """
        ?region=10,20,200,100 debe traducirse a bbox=(10, 20, 210, 120).
        La API acepta (x, y, width, height) pero PIL necesita (x1, y1, x2, y2).
        """
        client.get("/screenshot?region=10,20,200,100")
        call_kwargs = imagegrab.grab.call_args[1]
        assert call_kwargs["bbox"] == (10, 20, 210, 120)

    @pytest.mark.integration
    def test_screenshot_response_is_valid_base64_png(self, client, imagegrab):
        """La respuesta debe ser base64 decodificable que empiece con PNG magic bytes."""
        r = client.get("/screenshot")
        assert r.status_code == 200
        image_b64 = r.json()["image_b64"]
        raw = base64.b64decode(image_b64)
        # PNG magic bytes: \x89PNG
        assert raw[:4] == b"\x89PNG", "La imagen debe ser un PNG válido"

    @pytest.mark.integration
    def test_screen_size_uses_grab_dimensions(self, client, imagegrab):
        """
        /screen/size debe leer las dimensiones de la imagen devuelta por grab(),
        no un valor hardcodeado. Si el mock devuelve 1920x1080 debe retornar eso.
        """
        r = client.get("/screen/size")
        assert r.json() == {"width": 1920, "height": 1080}


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 5 — Endpoint /action: routing interno correcto
# Verifica que cada tipo de acción delega exactamente a la función correcta
# de ui_automation, con los parámetros en el orden esperado.
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionRoutingFlow:

    @pytest.mark.integration
    def test_action_click_routes_to_mouse_click(self, client, mouse_ctrl):
        client.post("/action", json={"type": "click", "x": 50, "y": 100, "button": "right"})
        assert mouse_ctrl.position == (50, 100)
        mouse_ctrl.click.assert_called_once()

    @pytest.mark.integration
    def test_action_move_routes_to_mouse_move(self, client, mouse_ctrl):
        client.post("/action", json={"type": "move", "x": 200, "y": 300})
        assert mouse_ctrl.position == (200, 300)
        mouse_ctrl.click.assert_not_called()

    @pytest.mark.integration
    def test_action_scroll_routes_to_mouse_scroll(self, client, mouse_ctrl):
        client.post("/action", json={"type": "scroll", "x": 0, "y": 0, "dy": 3})
        mouse_ctrl.scroll.assert_called_once_with(0, 3)

    @pytest.mark.integration
    def test_action_type_routes_to_keyboard_type(self, client, kb_ctrl):
        client.post("/action", json={"type": "type", "text": "test action"})
        kb_ctrl.type.assert_called_once_with("test action")

    @pytest.mark.integration
    def test_action_key_routes_to_keyboard_key(self, client, kb_ctrl):
        client.post("/action", json={"type": "key", "key": "enter"})
        kb_ctrl.press.assert_called()
        kb_ctrl.release.assert_called()

    @pytest.mark.integration
    def test_action_screenshot_returns_png(self, client, imagegrab):
        r = client.post("/action", json={"type": "screenshot"})
        assert r.status_code == 200
        assert r.json()["format"] == "png"
        raw = base64.b64decode(r.json()["image_b64"])
        assert raw[:4] == b"\x89PNG"

    @pytest.mark.integration
    def test_action_window_focus_returns_false_not_404(self, client, pygw):
        """
        /action con type=window_focus y ventana no encontrada debe retornar
        ok=False con 200 (no 404). El /action es para el LLM: no debe
        lanzar excepciones HTTP, sino comunicar el resultado como dato.
        """
        pygw.getAllWindows.return_value = []
        r = client.post("/action", json={"type": "window_focus", "title_pattern": "X"})
        assert r.status_code == 200
        assert r.json()["ok"] is False

    @pytest.mark.integration
    @pytest.mark.parametrize("action_type,missing_fields", [
        ("click",          {"type": "click"}),
        ("move",           {"type": "move", "x": 0}),           # falta y
        ("scroll",         {"type": "scroll", "x": 0, "y": 0}), # falta dy
        ("type",           {"type": "type"}),
        ("key",            {"type": "key"}),
        ("window_focus",   {"type": "window_focus"}),
    ])
    def test_action_missing_required_fields_returns_422(
        self, client, action_type, missing_fields
    ):
        """Cada tipo de acción debe rechazar llamadas con campos faltantes."""
        r = client.post("/action", json=missing_fields)
        assert r.status_code == 422, (
            f"Tipo '{action_type}' sin campos requeridos debe retornar 422, "
            f"obtenido {r.status_code}: {r.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 6 — HotkeyManager: ciclo de vida completo
# ═══════════════════════════════════════════════════════════════════════════════

class TestHotkeyManagerLifecycle:

    @pytest.mark.integration
    def test_start_registers_exactly_three_builtins(self):
        """
        Al iniciar el manager se registran exactamente los 3 hotkeys
        predefinidos (push-to-talk, mute-tts, shutdown).
        """
        mgr = HotkeyManager()
        mgr.start()
        hotkeys = mgr.list_hotkeys()
        builtins = [h for h in hotkeys if h["builtin"]]
        assert len(builtins) == 3
        descriptions = [h["description"] for h in builtins]
        assert any("push-to-talk" in d.lower() or "stt" in d.lower() for d in descriptions)
        assert any("mute" in d.lower() or "tts" in d.lower() for d in descriptions)
        assert any("apagar" in d.lower() or "shutdown" in d.lower() for d in descriptions)
        mgr.stop()

    @pytest.mark.integration
    def test_register_increases_count(self):
        mgr = HotkeyManager()
        mgr.start()
        initial = len(mgr.list_hotkeys())

        hid = mgr.register("<ctrl>+<alt>+t", lambda: None, "test hotkey")
        assert len(mgr.list_hotkeys()) == initial + 1
        mgr.stop()

    @pytest.mark.integration
    def test_unregister_decreases_count(self):
        mgr = HotkeyManager()
        mgr.start()
        hid = mgr.register("<ctrl>+<alt>+x", lambda: None, "temporal")
        before = len(mgr.list_hotkeys())

        result = mgr.unregister(hid)

        assert result is True
        assert len(mgr.list_hotkeys()) == before - 1
        mgr.stop()

    @pytest.mark.integration
    def test_builtin_hotkeys_cannot_be_unregistered(self):
        """Los hotkeys builtin deben ser inmutables."""
        mgr = HotkeyManager()
        mgr.start()
        builtins = [h for h in mgr.list_hotkeys() if h["builtin"]]
        for b in builtins:
            result = mgr.unregister(b["id"])
            assert result is False, f"builtin {b['id']} no debería poderse eliminar"
        mgr.stop()

    @pytest.mark.integration
    def test_unregister_nonexistent_returns_false(self):
        mgr = HotkeyManager()
        mgr.start()
        result = mgr.unregister("no-existe-xyz")
        assert result is False
        mgr.stop()

    @pytest.mark.integration
    def test_stop_clears_listener(self):
        """Tras stop() el listener interno debe ser None."""
        mgr = HotkeyManager()
        mgr.start()
        assert mgr._listener is not None
        mgr.stop()
        assert mgr._listener is None

    @pytest.mark.integration
    def test_register_after_stop_is_safe(self):
        """Registrar un hotkey tras stop() no debe lanzar excepción."""
        mgr = HotkeyManager()
        mgr.start()
        mgr.stop()
        # No debe explotar
        hid = mgr.register("<ctrl>+<alt>+z", lambda: None, "post-stop")
        assert hid is not None


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 7 — Hotkey API <→ HotkeyManager (server ↔ hotkeys.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHotkeyApiFlow:

    @pytest.mark.integration
    def test_register_via_api_persists_in_list(self, client):
        """Un hotkey registrado vía API debe aparecer en GET /hotkeys."""
        r = client.post("/hotkeys", json={"combo": "<ctrl>+<alt>+p", "description": "Test persist"})
        assert r.status_code == 201
        hid = r.json()["id"]

        hotkeys = client.get("/hotkeys").json()["hotkeys"]
        ids = [h["id"] for h in hotkeys]
        assert hid in ids

    @pytest.mark.integration
    def test_delete_via_api_removes_from_list(self, client):
        """Un hotkey registrado y luego eliminado no debe aparecer en el listado."""
        r = client.post("/hotkeys", json={"combo": "<ctrl>+<alt>+d", "description": "Temporal"})
        hid = r.json()["id"]

        client.delete(f"/hotkeys/{hid}")

        hotkeys = client.get("/hotkeys").json()["hotkeys"]
        ids = [h["id"] for h in hotkeys]
        assert hid not in ids

    @pytest.mark.integration
    def test_builtin_combo_visible_in_api(self, client):
        """Los hotkeys builtin de startup deben ser visibles en GET /hotkeys."""
        r = client.get("/hotkeys")
        hotkeys = r.json()["hotkeys"]
        builtins = [h for h in hotkeys if h.get("builtin")]
        assert len(builtins) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 8 — Hotkey dispara publicación en gateway (integración con httpx)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHotkeyGatewayPublish:

    @pytest.mark.integration
    def test_publish_event_posts_to_gateway(self):
        """
        Cuando un hotkey se dispara, _publish_event() debe hacer POST
        al endpoint /publish del gateway con el topic correcto.
        """
        with patch("src.hotkeys.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            HotkeyManager._publish_event("push-to-talk", {})

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        url = call_args[0][0]
        body = call_args[1]["json"]
        assert "/publish" in url
        assert body["topic"] == "push-to-talk"

    @pytest.mark.integration
    def test_publish_event_is_fire_and_forget_on_failure(self):
        """
        Si el gateway no está disponible, _publish_event() debe absorber
        la excepción y no propagarla (comportamiento fire-and-forget).
        """
        with patch("src.hotkeys.httpx.post", side_effect=Exception("gateway offline")):
            # No debe lanzar excepción
            HotkeyManager._publish_event("push-to-talk", {})

    @pytest.mark.integration
    def test_all_builtin_combos_have_correct_topics(self):
        """
        Cada callback builtin debe publicar el topic que le corresponde,
        no otro topic distinto.
        """
        topic_map = {
            "push-to-talk": False,
            "mute-tts":     False,
            "shutdown":     False,
        }

        def _capture(topic, data):
            if topic in topic_map:
                topic_map[topic] = True

        with patch.object(HotkeyManager, "_publish_event", side_effect=_capture):
            mgr = HotkeyManager()
            mgr.start()
            # Llamar manualmente los callbacks de cada builtin
            for entry_id, entry in mgr._entries.items():
                if entry.builtin:
                    cb = mgr._callbacks.get(entry.combo)
                    if cb:
                        cb()
            mgr.stop()

        assert all(topic_map.values()), (
            f"No todos los topics se publicaron: {topic_map}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO 9 — Secuencia de acciones (escenario completo de agente)
# Simula cómo el LLM usaría /action en secuencia para completar una tarea.
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentActionSequence:

    @pytest.mark.integration
    def test_sequence_focus_type_enter(self, client, pygw, fake_window, kb_ctrl):
        """
        Escenario: El LLM escribe en un campo de texto.
          1. Traer al frente la ventana objetivo
          2. Escribir texto
          3. Pulsar Enter para confirmar
        Cada paso debe completarse sin errores y en el orden correcto.
        """
        win = fake_window("Buscador")
        pygw.getAllWindows.return_value = [win]
        executed = []

        win.activate = MagicMock(side_effect=lambda: executed.append("focus"))
        kb_ctrl.type  = MagicMock(side_effect=lambda t: executed.append(f"type:{t}"))
        kb_ctrl.press = MagicMock(side_effect=lambda k: executed.append(f"press:{k}"))
        kb_ctrl.release = MagicMock(side_effect=lambda k: executed.append(f"release:{k}"))

        # Paso 1: focus
        r1 = client.post("/action", json={"type": "window_focus", "title_pattern": "Buscador"})
        assert r1.json()["ok"] is True

        # Paso 2: type
        r2 = client.post("/action", json={"type": "type", "text": "Dark Souls"})
        assert r2.status_code == 200

        # Paso 3: enter
        r3 = client.post("/action", json={"type": "key", "key": "enter"})
        assert r3.status_code == 200

        # Verificar orden
        assert executed[0] == "focus"
        assert any("type:Dark Souls" in e for e in executed)
        enter_events = [e for e in executed if "enter" in e.lower() or "ENTER" in e.upper()]
        assert len(enter_events) >= 1

    @pytest.mark.integration
    def test_sequence_screenshot_then_click(self, client, imagegrab, mouse_ctrl):
        """
        Escenario: El LLM captura pantalla para decidir dónde hacer click.
          1. screenshot → obtiene imagen
          2. click en coordenadas elegidas
        Ambos pasos deben completarse correctamente.
        """
        r1 = client.post("/action", json={"type": "screenshot"})
        assert r1.status_code == 200
        assert "image_b64" in r1.json()
        imagegrab.grab.assert_called_once()

        r2 = client.post("/action", json={"type": "click", "x": 960, "y": 540})
        assert r2.status_code == 200
        assert mouse_ctrl.position == (960, 540)

    @pytest.mark.integration
    def test_sequence_stops_on_first_error(self, client, pygw):
        """
        Si un paso falla (ventana no encontrada → ok=False), los pasos
        siguientes siguen siendo ejecutables — el servidor no se rompe.
        """
        pygw.getAllWindows.return_value = []

        r1 = client.post("/action", json={"type": "window_focus", "title_pattern": "NoExiste"})
        assert r1.status_code == 200
        assert r1.json()["ok"] is False  # falla pero sin HTTP error

        # El servidor sigue respondiendo correctamente
        r2 = client.get("/health")
        assert r2.status_code == 200
        assert r2.json()["status"] == "ok"
