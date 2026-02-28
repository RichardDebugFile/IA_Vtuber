"""
Test de fish-speech (openaudio-s1-mini) — repo local
Venv: services/tts-fish/venv
Referencia: casiopy-V2/CasiopyVoz-15s.wav
"""
import sys, time, wave
from pathlib import Path

import numpy as np
import torch

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

SERVICE_DIR = Path(__file__).parent
REPO_DIR    = SERVICE_DIR / "repo"
CKPT_DIR    = REPO_DIR / "checkpoints" / "openaudio-s1-mini"
OUTPUT_DIR  = SERVICE_DIR / "outputs"
REF_AUDIO   = SERVICE_DIR.parent.parent / "casiopy-V2" / "CasiopyVoz-15s.wav"
REF_TEXT    = "¡Oh! Con que te quedó dudas sobre Mochi, ¿mmmm? Bien te concederé un desvío de nuestras tareas en mano. Ya que lo pediste de forma tan amable y tierna."

sys.path.insert(0, str(REPO_DIR))
import os
os.chdir(REPO_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

TEXTS = [
    "Hola, esta es una prueba del sistema de sintesis de voz en espanol.",
    "La inteligencia artificial esta transformando la forma en que interactuamos con la tecnologia moderna.",
    "Buenos dias, como puedo ayudarte hoy? Estoy aqui para lo que necesites.",
]

SEP  = "-" * 60
SEP2 = "=" * 60

def save_wav(audio: np.ndarray, sr: int, path: Path):
    if audio.dtype != np.int16:
        audio = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(SEP2)
    print("  fish-speech (openaudio-s1-mini) — Test local")
    print(SEP2)
    print(f"  Device : {device}")
    if torch.cuda.is_available():
        print(f"  GPU    : {torch.cuda.get_device_name(0)}")
        print(f"  VRAM   : {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB total")
        torch.cuda.reset_peak_memory_stats()
    print(f"  Ref    : {REF_AUDIO}")

    if not REF_AUDIO.exists():
        print(f"  ERROR: audio de referencia no encontrado")
        sys.exit(1)
    if not (CKPT_DIR / "model.pth").exists():
        print(f"  ERROR: modelo no encontrado en {CKPT_DIR}")
        sys.exit(1)

    print(SEP)

    print("\nCargando modelos (LLM + DAC codec)...")
    t0 = time.time()
    from tools.server.model_manager import ModelManager
    from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio

    manager = ModelManager(
        mode="tts",
        device=device,
        half=False,
        compile=False,
        llama_checkpoint_path=str(CKPT_DIR),
        decoder_checkpoint_path=str(CKPT_DIR / "codec.pth"),
        decoder_config_name="modded_dac_vq",
    )
    t_load = time.time() - t0
    vram_l = torch.cuda.memory_allocated(0) / 1e9 if device == "cuda" else 0
    print(f"  OK en {t_load:.1f}s | VRAM: {vram_l:.2f} GB")
    print(SEP)

    ref_bytes = REF_AUDIO.read_bytes()
    engine    = manager.tts_inference_engine
    results   = []

    for i, text in enumerate(TEXTS):
        print(f"\n  [{i+1}/{len(TEXTS)}] {len(text)} chars")
        print(f"  \"{text[:60]}...\"" if len(text) > 60 else f"  \"{text}\"")
        if i == 0:
            print("  (primera inferencia — warmup CUDA)")

        req = ServeTTSRequest(
            text=text,
            references=[ServeReferenceAudio(audio=ref_bytes, text=REF_TEXT)],
            format="wav",
            chunk_length=200,
            temperature=0.8,
            top_p=0.8,
            repetition_penalty=1.1,
            max_new_tokens=1024,
        )

        if device == "cuda":
            torch.cuda.synchronize()
        t_start = time.perf_counter()

        audio_arr, sr = None, 44100
        for result in engine.inference(req):
            if result.code == "error":
                print(f"  ERROR: {result.error}")
                break
            elif result.code == "final" and result.audio is not None:
                sr, audio_arr = result.audio[0], result.audio[1]

        if device == "cuda":
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - t_start

        if audio_arr is None:
            print("  ERROR: no se generó audio")
            continue

        dur  = len(audio_arr) / sr
        rtf  = elapsed / dur if dur > 0 else 0
        vram = torch.cuda.memory_allocated(0) / 1e9 if device == "cuda" else 0
        tag  = "FAST" if rtf < 1.0 else "SLOW"

        out = OUTPUT_DIR / f"fish_{i+1}.wav"
        save_wav(audio_arr, sr, out)
        print(f"  T {elapsed:.2f}s | Audio {dur:.2f}s | RTF {rtf:.3f} [{tag}] | VRAM {vram:.2f} GB")
        print(f"  Guardado: {out}")
        results.append((text[:40], elapsed, rtf))

    print(f"\n{SEP2}")
    print("  RESUMEN")
    print(SEP2)
    if results:
        rtfs = [r[2] for r in results]
        print(f"  RTF avg       : {sum(rtfs)/len(rtfs):.3f}")
        print(f"  VRAM peak     : {torch.cuda.max_memory_allocated(0)/1e9:.2f} GB")
    print(f"  Salidas       : {OUTPUT_DIR}")
    print(SEP2)

if __name__ == "__main__":
    main()
