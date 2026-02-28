"""
Test de Qwen3-TTS — repo local
Venv: services/tts-qwen3/venv
Referencia: casiopy-V2/CasiopyVoz-15s.wav
"""
import os, sys, time
from pathlib import Path

SERVICE_DIR = Path(__file__).parent
REPO_DIR    = SERVICE_DIR / "repo"
MODEL_DIR   = REPO_DIR / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
OUTPUT_DIR  = SERVICE_DIR / "outputs"
REF_AUDIO   = SERVICE_DIR.parent.parent / "casiopy-V2" / "CasiopyVoz-15s.wav"
REF_TEXT    = "¡Oh! Con que te quedó dudas sobre Mochi, ¿mmmm? Bien te concederé un desvío de nuestras tareas en mano. Ya que lo pediste de forma tan amable y tierna."

sys.path.insert(0, str(REPO_DIR))
OUTPUT_DIR.mkdir(exist_ok=True)

import torch
import soundfile as sf

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

TESTS = [
    {"name": "corto",  "text": "Hola, que tal? Espero que todo vaya bien hoy.",          "out": "qwen3_corto.wav"},
    {"name": "medio",  "text": ("Buenos dias. Realizamos una prueba de generacion de voz "
                                "con este modelo. El objetivo es evaluar la calidad y velocidad "
                                "de sintesis en espanol."),                                "out": "qwen3_medio.wav"},
    {"name": "largo",  "text": ("La tecnologia de clonacion de voz ha avanzado enormemente, "
                                "permitiendo sintetizar cualquier voz con solo unos segundos de audio. "
                                "Estos modelos capturan el timbre, la entonacion y las caracteristicas "
                                "prosodicas del hablante original con resultados muy naturales."),
                                                                                           "out": "qwen3_largo.wav"},
]

SEP  = "-" * 60
SEP2 = "=" * 60

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(SEP2)
    print("  Qwen3-TTS — Test local")
    print(SEP2)
    print(f"  Device : {device}")
    if torch.cuda.is_available():
        print(f"  GPU    : {torch.cuda.get_device_name(0)}")
        torch.cuda.reset_peak_memory_stats()
    print(f"  Ref    : {REF_AUDIO}")
    if not REF_AUDIO.exists():
        print(f"  ERROR: audio de referencia no encontrado")
        sys.exit(1)
    print(SEP)

    print("\nCargando modelo...")
    t0 = time.time()
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(
        str(MODEL_DIR),
        device_map=device,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    t_load = time.time() - t0
    vram_l = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
    print(f"  OK en {t_load:.1f}s | VRAM: {vram_l:.0f} MB")

    print("\nExtrayendo speaker embedding...")
    t0 = time.time()
    prompt_items = model.create_voice_clone_prompt(
        ref_audio=str(REF_AUDIO),
        ref_text=REF_TEXT,
        x_vector_only_mode=False,
    )
    print(f"  OK en {time.time()-t0:.2f}s")
    print(SEP)

    results = []
    for i, test in enumerate(TESTS):
        print(f"\n  [{test['name'].upper()}] {len(test['text'])} chars")
        if i == 0:
            print("  (primera inferencia — warmup CUDA)")

        t0 = time.time()
        wavs, sr = model.generate_voice_clone(
            text=test["text"],
            language="Spanish",
            voice_clone_prompt=prompt_items,
        )
        t_gen = time.time() - t0

        out = OUTPUT_DIR / test["out"]
        sf.write(str(out), wavs[0], sr)

        dur  = len(wavs[0]) / sr
        rtf  = t_gen / dur if dur > 0 else 0
        vram = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
        tag  = "FAST" if rtf < 1.0 else "SLOW"
        print(f"  T_gen {t_gen:.2f}s | Audio {dur:.2f}s | RTF {rtf:.3f} [{tag}] | VRAM {vram:.0f} MB")
        print(f"  Guardado: {out}")
        results.append((test["name"], dur, t_gen, rtf, vram))

    print(f"\n{SEP2}")
    print("  RESUMEN")
    print(SEP2)
    warm  = results[1:]
    rtfs  = [r[3] for r in warm] if warm else [r[3] for r in results]
    print(f"  RTF avg (warm): {sum(rtfs)/len(rtfs):.3f}")
    print(f"  VRAM peak     : {torch.cuda.max_memory_allocated()/1024**2:.0f} MB")
    print(f"  Salidas       : {OUTPUT_DIR}")
    print(SEP2)

if __name__ == "__main__":
    main()
