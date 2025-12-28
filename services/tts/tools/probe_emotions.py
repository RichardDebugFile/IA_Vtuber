# Codigo para probar desde consola: python -m src.probe_emotions
# Pero no olvidar estar en el path de services/tts 

from __future__ import annotations
import io, os, sys, wave, json
from pathlib import Path
from typing import Dict, Any

# Ejecutar como módulo y script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(__file__))

# Carga .env (local y raíz)
# IMPORTANTE: override=True para que el .env tenga prioridad sobre variables del sistema
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=True)
except Exception:
    pass

try:
    from .engine_http import HTTPFishEngine
except ImportError:
    from engine_http import HTTPFishEngine  # fallback

EMOS = [
    "neutral","happy","angry","sad","thinking","surprised",
    "sleeping","upset","fear","asco","love","bored","excited","confused"
]

PHRASES: Dict[str, str] = {
    "neutral":   "Prueba neutral para mapeo de emociones.",
    "happy":     "¡Estoy muy feliz de estar aquí!",
    "angry":     "Esto me molesta bastante, honestamente.",
    "sad":       "Hoy me siento un poco triste.",
    "thinking":  "Déjame pensar un segundo para responder.",
    "surprised": "¡Vaya, eso sí que no me lo esperaba!",
    "sleeping":  "Me da un poco de sueño en este momento.",
    "upset":     "No es justo lo que está pasando.",
    "fear":      "Tengo miedo de que algo salga mal.",
    "asco":      "Puaj, eso me da muchísimo asco.",
    "love":      "Te aprecio con todo mi corazón.",
    "bored":     "Esto se está poniendo un poco aburrido.",
    "excited":   "¡Qué emoción, no puedo esperar más!",
    "confused":  "No entiendo muy bien lo que está ocurriendo.",
}

def is_wav(b: bytes) -> bool:
    return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE"

def wav_info(b: bytes) -> Dict[str, Any]:
    try:
        with wave.open(io.BytesIO(b), "rb") as wf:
            return {
                "channels":  wf.getnchannels(),
                "sampwidth": wf.getsampwidth(),
                "framerate": wf.getframerate(),
                "nframes":   wf.getnframes(),
                "dur_sec":   round(wf.getnframes() / max(1, wf.getframerate()), 3),
            }
    except Exception as e:
        return {"error": str(e)}

def main() -> None:
    outdir = Path("_out/emotions")
    outdir.mkdir(parents=True, exist_ok=True)

    http = HTTPFishEngine(os.getenv("FISH_TTS_HTTP"))
    if not http.health():
        print("[warn] Fish HTTP /health no responde (se intentará igual).")

    report = []
    for emo in EMOS:
        txt = PHRASES.get(emo, f"Prueba emoción {emo}")
        print(f"→ {emo}")
        try:
            audio = http.synthesize(txt, emo)
            if not is_wav(audio):
                raise RuntimeError("No es WAV (RIFF).")
            info = wav_info(audio)
            (outdir / f"{emo}.wav").write_bytes(audio)
            report.append({"emotion": emo, "ok": True, "info": info})
            print(f"   OK  {info}")
        except Exception as e:
            report.append({"emotion": emo, "ok": False, "error": str(e)})
            print(f"   FAIL  {e}")

    (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen → {outdir / 'report.json'}")

if __name__ == "__main__":
    main()
