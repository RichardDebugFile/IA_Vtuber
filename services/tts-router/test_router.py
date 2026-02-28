"""
Prueba integrada del tts-router.
Para cada backend: inicia -> espera carga -> sintetiza -> detiene.

Uso:
  python test_router.py                   # prueba los 4 backends
  python test_router.py stream_fast       # prueba solo ese backend
  python test_router.py stream_fast content_fish  # dos backends

Requisito: el router debe estar corriendo en http://127.0.0.1:8810
  Ejecuta start.bat desde esta misma carpeta.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import json
import time
import base64
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROUTER     = "http://127.0.0.1:8810"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

TEST_TEXT = (
    "Buenos días. Esta es una prueba integrada del router de síntesis de voz. "
    "Verificando que el sistema funciona correctamente de extremo a extremo."
)

SEP  = "-" * 60
SEP2 = "=" * 60


# ── HTTP helpers (stdlib, sin deps extra) ─────────────────────────────────────

def _http(method: str, url: str, data=None, timeout=10):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_text[:200]}") from e
    except URLError as e:
        raise RuntimeError(f"No se pudo conectar a {url}: {e.reason}") from e


def get(url, timeout=5):
    return _http("GET", url, timeout=timeout)


def post(url, data=None, timeout=10):
    return _http("POST", url, data=data, timeout=timeout)


# ── Lógica de prueba ──────────────────────────────────────────────────────────

def wait_for_model(mode: str, timeout: int = 300) -> bool:
    """Sondea /backends/{mode} hasta que model_loaded=true o timeout."""
    deadline        = time.time() + timeout
    last_line       = ""
    # Esperamos que el proceso haya arrancado uvicorn antes de detectar muerte temprana
    proc_was_seen   = False

    while time.time() < deadline:
        time.sleep(5)
        try:
            s = get(f"{ROUTER}/backends/{mode}", timeout=15)
        except Exception as e:
            line = f"  sondeo error: {e}"
            if line != last_line:
                print(line, flush=True)
                last_line = line
            continue

        proc    = s.get("process_running", False)
        online  = s.get("online", False)
        loading = s.get("loading", False)
        loaded  = s.get("model_loaded", False)
        err     = s.get("error")

        line = f"  proc={proc}  online={online}  loading={loading}  loaded={loaded}"
        if err:
            line += f"  error={err[:80]}"
        if line != last_line:
            print(line, flush=True)
            last_line = line

        if loaded:
            return True

        if proc:
            proc_was_seen = True

        # El proceso murió después de haber arrancado → error real
        if proc_was_seen and not proc and not loaded:
            print("  ERROR: el proceso terminó sin cargar el modelo.", flush=True)
            return False

    print(f"  TIMEOUT ({timeout}s) esperando modelo.", flush=True)
    return False


def test_mode(mode: str) -> bool:
    print(f"\n{SEP2}")
    print(f"  BACKEND: {mode}")
    print(SEP2)

    # ── 1. Iniciar proceso ────────────────────────────────────────────────────
    print("[1/4] Iniciando backend...")
    try:
        r = post(f"{ROUTER}/backends/{mode}/start", timeout=10)
        print(f"  {r.get('message', r)}")
    except RuntimeError as e:
        print(f"  ERROR al iniciar: {e}")
        return False

    # ── 2. Esperar carga del modelo ───────────────────────────────────────────
    print("[2/4] Esperando que el modelo cargue...")
    if not wait_for_model(mode):
        try:
            post(f"{ROUTER}/backends/{mode}/stop", timeout=10)
        except Exception:
            pass
        return False
    print("  [OK] Modelo listo")

    # ── 3. Sintetizar audio ───────────────────────────────────────────────────
    print("[3/4] Sintetizando audio via router...")
    try:
        result = post(
            f"{ROUTER}/synthesize",
            data={"text": TEST_TEXT, "voice": "casiopy", "mode": mode},
            timeout=300,
        )
    except RuntimeError as e:
        print(f"  ERROR en síntesis: {e}")
        try:
            post(f"{ROUTER}/backends/{mode}/stop", timeout=10)
        except Exception:
            pass
        return False

    if not result.get("ok"):
        print(f"  ERROR: respuesta inesperada: {result}")
        return False

    dur     = result.get("duration_s", 0)
    rtf     = result.get("rtf", 0)
    backend = result.get("backend", "?")
    sr      = result.get("sample_rate", 0)
    print(f"  [OK] duration={dur:.2f}s  RTF={rtf:.3f}  backend={backend}  sr={sr}Hz")

    # Guardar audio (bytes ya vienen en WAV)
    try:
        raw = base64.b64decode(result["audio_b64"])
        out = OUTPUT_DIR / f"router_test_{mode}.wav"
        out.write_bytes(raw)
        print(f"  [OK] Guardado: outputs/router_test_{mode}.wav")
    except Exception as e:
        print(f"  WARN: no se pudo guardar el audio: {e}")

    # ── 4. Detener proceso ────────────────────────────────────────────────────
    print("[4/4] Deteniendo backend...")
    try:
        r = post(f"{ROUTER}/backends/{mode}/stop", timeout=15)
        print(f"  [OK] {r.get('message', r)}")
    except RuntimeError as e:
        print(f"  WARN al detener: {e}")

    # Pausa para que la GPU libere VRAM antes del próximo backend
    time.sleep(5)
    return True


def main():
    all_modes  = ["stream_fast", "stream_quality", "content", "content_fish"]
    test_modes = sys.argv[1:] if len(sys.argv) > 1 else all_modes

    # Verificar que el router está corriendo
    print(f"\n{SEP2}")
    print("  TTS Router - Prueba integrada")
    print(SEP2)
    print("Verificando router en", ROUTER)
    try:
        h = get(f"{ROUTER}/health", timeout=5)
        print(f"  [OK] Router activo  |  backends: {h.get('backends', [])}  |  running: {h.get('running', [])}")
    except RuntimeError as e:
        print(f"  ERROR: Router no disponible.\n  {e}")
        print("\n  → Inicia el router primero ejecutando start.bat en esta carpeta.")
        sys.exit(1)

    invalid = [m for m in test_modes if m not in all_modes]
    if invalid:
        print(f"\n  Modos inválidos: {invalid}")
        print(f"  Modos válidos:   {all_modes}")
        sys.exit(1)

    print(f"\n  Backends a probar: {test_modes}")
    print(f"  Texto de prueba: \"{TEST_TEXT[:60]}...\"")

    results: dict[str, bool] = {}
    for mode in test_modes:
        results[mode] = test_mode(mode)

    # Resumen final
    print(f"\n{SEP2}")
    print("  RESUMEN")
    print(SEP2)
    ok_all = True
    for mode, ok in results.items():
        status = "OK     " if ok else "FALLIDO"
        print(f"  {mode:<20s}  {status}")
        if not ok:
            ok_all = False
    print(SEP2)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
