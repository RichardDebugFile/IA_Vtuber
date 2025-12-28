from __future__ import annotations
import argparse, io, os, sys, wave, json
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Ejecutar como script o módulo
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(__file__))

try:
    import httpx, ormsgpack  # type: ignore
except Exception:
    httpx = None
    ormsgpack = None

# Mapping de emociones (opcional)
PRESETS_PATH = os.path.join(os.path.dirname(__file__), "voices", "presets.yaml")
EMO_MAP: Dict[str, str] = {}
if os.path.isfile(PRESETS_PATH):
    try:
        import yaml  # type: ignore
        with open(PRESETS_PATH, "r", encoding="utf-8") as f:
            EMO_MAP = yaml.safe_load(f) or {}
    except Exception:
        EMO_MAP = {}


def is_wav(b: bytes) -> bool:
    return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE"


def wav_info(b: bytes) -> Dict[str, Any]:
    try:
        with wave.open(io.BytesIO(b), "rb") as wf:
            return {
                "channels": wf.getnchannels(),
                "sampwidth": wf.getsampwidth(),
                "framerate": wf.getframerate(),
                "nframes": wf.getnframes(),
                "dur_sec": round(wf.getnframes() / max(1, wf.getframerate()), 3),
            }
    except Exception as e:
        return {"error": str(e)}


@dataclass
class ProbeResult:
    ok: bool
    detail: str
    extra: Dict[str, Any] | None = None


def _marker(emotion: str) -> str:
    return EMO_MAP.get(emotion, EMO_MAP.get("neutral", "neutral")) or (emotion or "neutral")


def synth_msgpack(url: str, text: str, emotion: str) -> ProbeResult:
    if httpx is None or ormsgpack is None:
        return ProbeResult(False, "Faltan deps: pip install httpx ormsgpack")
    payload = {"text": f"({_marker(emotion)}) {text}", "format": "wav"}
    headers = {"Content-Type": "application/msgpack"}
    try:
        r = httpx.post(url, content=ormsgpack.packb(payload), headers=headers, timeout=600.0)
        r.raise_for_status()
        data = r.content
        if not is_wav(data):
            return ProbeResult(False, f"No es WAV (ctype={r.headers.get('content-type')})")
        return ProbeResult(True, f"WAV OK: {wav_info(data)}", {"bytes": len(data), "wav": wav_info(data), "raw": data})
    except httpx.HTTPStatusError as e:
        return ProbeResult(False, f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return ProbeResult(False, f"Error: {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Smoke test Fish/OpenAudio TTS (MessagePack)")
    ap.add_argument("--url", default=os.getenv("FISH_TTS_HTTP", "http://127.0.0.1:8080/v1/tts"))
    ap.add_argument("--out", default="probe.wav")
    ap.add_argument("--text", default="Esto es una prueba de voz en español.")
    ap.add_argument("--emotion", default="neutral")
    args = ap.parse_args()

    res = synth_msgpack(args.url, args.text, args.emotion)
    print(("OK" if res.ok else "FAIL"), "-", res.detail)
    if res.ok and res.extra and "raw" in res.extra:
        with open(args.out, "wb") as f:
            f.write(res.extra["raw"])
        print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
