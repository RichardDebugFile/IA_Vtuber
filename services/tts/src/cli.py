from __future__ import annotations
import argparse, io, wave, sys, os, time
from typing import Optional

# Ejecutable como módulo o script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(__file__))

# ---- Cargar .env tanto en services/tts/.env como en la raíz ----
from pathlib import Path
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
except Exception:
    pass

# Engines
try:
    from .engine import TTSEngine
except ImportError:
    from engine import TTSEngine  # fallback

try:
    from .engine_http import HTTPFishEngine
except Exception:
    HTTPFishEngine = None  # si falta httpx/ormsgpack

# Gestor del servidor Fish
try:
    from .fish_server import FishServerConfig, FishServerManager, FishServerError
except Exception:
    FishServerConfig = FishServerManager = FishServerError = None  # noqa

# Repro
try:
    import simpleaudio as sa  # type: ignore
except Exception:
    sa = None


def save_wav(path: str, audio_bytes: bytes) -> None:
    with open(path, "wb") as f:
        f.write(audio_bytes)
    print(f"Audio written to {path}")


def play_audio(audio_bytes: bytes) -> None:
    if sa is None:
        save_wav("output.wav", audio_bytes)
        return
    try:
        with wave.open(io.BytesIO(audio_bytes)) as wf:
            obj = sa.WaveObject(
                wf.readframes(wf.getnframes()),
                wf.getnchannels(),
                wf.getsampwidth(),
                wf.getframerate(),
            )
        obj.play().wait_done()
    except Exception:
        save_wav("output.wav", audio_bytes)


def autostart_fish_if_needed(url: str, verbose: bool = True, timeout_s: int = 180) -> None:
    """
    Si el /health no responde y hay variables en .env, lanza tools.api_server.
    """
    if HTTPFishEngine is None or FishServerManager is None:
        return  # no tenemos dependencias para HTTP o manager

    http = HTTPFishEngine(url)
    try:
        if http.health():
            return
    except Exception:
        pass

    # Leer rutas desde .env
    repo = os.getenv("FISH_REPO", "")
    vpy  = os.getenv("FISH_VENV_PY", "")
    ckpt = os.getenv("FISH_CKPT", "")
    if not (repo and vpy and ckpt):
        # No podemos autostart sin rutas
        return

    if verbose:
        print("[info] Fish TTS no responde; intentando arrancar el servidor…")

    cfg = FishServerConfig(
        repo_dir=repo,
        venv_python=vpy,
        ckpt_dir=ckpt,
        host="127.0.0.1",
        port=int(url.split(":")[-1].split("/")[0]),  # extrae 8080 de http://127.0.0.1:8080/...
        log_path=str(Path(__file__).resolve().parents[1] / ".logs" / "fish_api.log"),
    )
    mgr = FishServerManager(cfg)
    try:
        mgr.start()
    except FishServerError as e:
        if verbose:
            print(f"[warn] No se pudo autoiniciar el server Fish: {e}")
        return

    # Pequeña espera extra (el manager ya hace health polling)
    time.sleep(0.5)
    if verbose:
        print("[info] Servidor Fish iniciado.")


def build_engine(backend: str, url: Optional[str], autostart: bool) -> object:
    """Devuelve un engine con .synthesize(text, emotion)->bytes"""
    backend = backend.lower()
    if backend in ("http", "auto") and HTTPFishEngine is not None:
        if autostart:
            autostart_fish_if_needed(url or "")

        http = HTTPFishEngine(url)
        if backend == "http":
            return http
        # auto: si HTTP está sano, úsalo; sino, cae a local
        try:
            if http.health():
                return http
        except Exception:
            pass

    # fallback: local transformers (o stub)
    return TTSEngine()


def main() -> None:
    p = argparse.ArgumentParser(description="TTS console utility")
    p.add_argument("text", help="Text to synthesize")
    p.add_argument("--emotion", default="neutral", help="Emotion preset")
    p.add_argument("--voice", default=None, help="Voice ID/name (if supported)")
    p.add_argument("--rate", type=float, default=None, help="Speech rate (e.g., 1.0=normal)")
    p.add_argument("--sr", type=int, default=None, help="Sample rate override (e.g., 24000)")
    p.add_argument("--out", default=None, help="Output wav path (if not set, try playback)")
    p.add_argument("--no-play", action="store_true", help="Do not playback; only save")
    p.add_argument("--backend", default="auto", choices=["auto", "http", "local"], help="Engine backend")
    p.add_argument("--url", default=os.getenv("FISH_TTS_HTTP", "http://127.0.0.1:8080/v1/tts"),
                   help="HTTP TTS endpoint (cuando backend=http/auto)")
    p.add_argument("--autostart", dest="autostart", action="store_true", default=True,
                   help="Intentar arrancar Fish server automáticamente (default: on)")
    p.add_argument("--no-autostart", dest="autostart", action="store_false",
                   help="No arrancar server automáticamente")
    args = p.parse_args()

    # kwargs reservados por si algún día el TTSEngine local los soporta
    _ = args.voice, args.rate, args.sr

    engine = build_engine(args.backend, args.url, args.autostart)
    audio = engine.synthesize(args.text, args.emotion)

    if args.out:
        save_wav(args.out, audio)
    elif args.no_play:
        save_wav("output.wav", audio)
    else:
        play_audio(audio)


if __name__ == "__main__":
    main()
