# services/tts/src/diag.py
from __future__ import annotations
import argparse, base64, io, json, os, sys, wave
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Permite ejecución como script y como módulo
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(__file__))

try:
    from .engine import TTSEngine
except ImportError:
    from engine import TTSEngine  # fallback

DEFAULT_MODEL_DIR = os.getenv("FISH_TTS_MODEL_DIR", os.path.join("models", "fish-speech"))
CONV_URL = os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")

REQUIRED_FILES = [
    "config.json",
    "model.pth",
    "tokenizer.json",          # algunos repos usan tokenizer.json
    "tokenizer_config.json",   # y/o tokenizer_config.json
    "special_tokens_map.json", # si existe, mejor
]

EMO_PROBES = [
    ("neutral",   "Prueba de audio en español."),
    ("joyful",    "Estoy muy contento de saludar a todos."),
    ("angry",     "No me gusta cuando el código falla."),
]

@dataclass
class CheckResult:
    ok: bool
    detail: str
    extra: Dict[str, Any] | None = None

class TTSDiagnostics:
    def __init__(self, model_dir: Optional[str] = None, conv_url: Optional[str] = None):
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self.conv_url = conv_url or CONV_URL
        self.errors: list[str] = []

    def check_deps(self) -> CheckResult:
        missing = []
        try:
            import transformers  # type: ignore
        except Exception:
            missing.append("transformers")
        try:
            import torch  # type: ignore
        except Exception:
            missing.append("torch")
        try:
            import numpy  # type: ignore
        except Exception:
            missing.append("numpy")
        detail = "OK" if not missing else f"Faltan dependencias: {', '.join(missing)}"
        return CheckResult(ok=not missing, detail=detail, extra={"missing": missing})

    def check_model_dir(self) -> CheckResult:
        if not os.path.isdir(self.model_dir):
            return CheckResult(False, f"No existe el directorio del modelo: {self.model_dir}")
        missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(self.model_dir, f))]
        if missing:
            return CheckResult(False, f"Faltan archivos en el modelo: {missing}", {"missing": missing})
        return CheckResult(True, f"Modelo encontrado en: {self.model_dir}")

    def check_conv_health(self) -> CheckResult:
        import httpx  # type: ignore
        url = f"{self.conv_url}/health"
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            return CheckResult(True, f"conversation /health OK: {data}", {"data": data})
        except Exception as e:
            return CheckResult(False, f"conversation /health falló: {e}")

    def load_engine(self) -> CheckResult:
        try:
            eng = TTSEngine(model_dir=self.model_dir)
            # interno: expone _pipeline o None
            ok = getattr(eng, "_pipeline", None) is not None
            return CheckResult(ok=ok, detail="Pipeline cargado" if ok else "Pipeline no disponible", extra={"loaded": ok})
        except Exception as e:
            return CheckResult(False, f"Error inicializando TTSEngine: {e}")

    @staticmethod
    def _is_wav(b: bytes) -> bool:
        return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE"

    @staticmethod
    def _wav_info(b: bytes) -> Dict[str, Any]:
        try:
            with wave.open(io.BytesIO(b), "rb") as wf:
                return {
                    "channels":  wf.getnchannels(),
                    "sampwidth": wf.getsampwidth(),
                    "framerate": wf.getframerate(),
                    "nframes":   wf.getnframes(),
                    "dur_sec":   round(wf.getnframes() / float(wf.getframerate() or 1), 3),
                }
        except Exception as e:
            return {"error": str(e)}

    def synth_probe(self, emotion: str, text: str, out_path: Optional[str] = None) -> CheckResult:
        try:
            eng = TTSEngine(model_dir=self.model_dir)
            audio = eng.synthesize(text, emotion)
            if not self._is_wav(audio):
                return CheckResult(False, "La salida no es WAV válido (RIFF). Verifica engine.py.")
            info = self._wav_info(audio)
            if out_path:
                with open(out_path, "wb") as f:
                    f.write(audio)
            return CheckResult(True, f"WAV OK ({info.get('framerate')} Hz, {info.get('dur_sec')} s)", {"wav": info})
        except Exception as e:
            return CheckResult(False, f"Error en síntesis: {e}")

    def conv_to_tts(self, user_text: str, out_path: str = "diag_conv.wav") -> CheckResult:
        import httpx  # type: ignore
        try:
            # 1) pregunta al microservicio conversation
            payload = {"user": "local", "text": user_text}
            r = httpx.post(f"{self.conv_url}/chat", json=payload, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            reply = data.get("reply", "")
            emotion = data.get("emotion", "neutral")
            if not reply:
                return CheckResult(False, f"conversation devolvió reply vacío: {data!r}")

            # 2) sintetiza con TTSEngine
            eng = TTSEngine(model_dir=self.model_dir)
            audio = eng.synthesize(reply, emotion)
            if not self._is_wav(audio):
                return CheckResult(False, "La salida no es WAV válido (RIFF) tras conversation.")
            with open(out_path, "wb") as f:
                f.write(audio)
            return CheckResult(True, f"End-to-end OK → {out_path}", {"reply": reply, "emotion": emotion})
        except Exception as e:
            return CheckResult(False, f"Fallo end-to-end: {e}")

def main():
    ap = argparse.ArgumentParser(description="Diagnóstico FishAudio TTS")
    ap.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    ap.add_argument("--conv-url", default=CONV_URL)
    ap.add_argument("--deep", action="store_true", help="Pruebas profundas (3 emociones + end-to-end)")
    args = ap.parse_args()

    diag = TTSDiagnostics(model_dir=args.model_dir, conv_url=args.conv_url)

    checks = [
        ("deps", diag.check_deps()),
        ("model_dir", diag.check_model_dir()),
        ("pipeline", diag.load_engine()),
        ("conv_health", diag.check_conv_health()),
    ]
    print("== Comprobaciones ==")
    for name, res in checks:
        print(f"[{name}] {'OK' if res.ok else 'FAIL'} - {res.detail}")

    # Smoke TTS
    print("\n== Prueba TTS simple ==")
    c = diag.synth_probe("neutral", "Esto es una prueba de voz con Fish Audio.", out_path="diag_neutral.wav")
    print(f"[synth.neutral] {'OK' if c.ok else 'FAIL'} - {c.detail}")

    if args.deep:
        for emo, txt in EMO_PROBES:
            out = f"diag_{emo}.wav"
            r = diag.synth_probe(emo, txt, out_path=out)
            print(f"[synth.{emo}] {'OK' if r.ok else 'FAIL'} - {r.detail}")

        print("\n== End-to-End (conversation→TTS) ==")
        e2e = diag.conv_to_tts("Hola, ¿cómo estás? Cuéntame algo breve.", out_path="diag_conv.wav")
        print(f"[e2e] {'OK' if e2e.ok else 'FAIL'} - {e2e.detail}")
        if e2e.extra:
            print("   Resumen:", json.dumps(e2e.extra, ensure_ascii=False))

if __name__ == "__main__":
    main()
