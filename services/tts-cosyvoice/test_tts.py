"""
Test de CosyVoice3-0.5B (Fun-CosyVoice3-0.5B) — repo local
Venv: services/tts-cosyvoice/venv
Referencia: casiopy-V2/CasiopyVoz-15s.wav
"""
import sys, time
from pathlib import Path

SERVICE_DIR = Path(__file__).parent
REPO_DIR    = SERVICE_DIR / "repo"
OUTPUT_DIR  = SERVICE_DIR / "outputs"
REF_AUDIO   = SERVICE_DIR.parent.parent / "casiopy-V2" / "CasiopyVoz-15s.wav"
# Fun-CosyVoice3 requiere "<|endofprompt|>" separando el system prompt de la transcripción
REF_TEXT    = "You are a helpful assistant.<|endofprompt|>¡Oh! Con que te quedó dudas sobre Mochi, ¿mmmm? Bien te concederé un desvío de nuestras tareas en mano. Ya que lo pediste de forma tan amable y tierna."

sys.path.insert(0, str(REPO_DIR))
sys.path.insert(0, str(REPO_DIR / "third_party" / "Matcha-TTS"))
import os
os.chdir(REPO_DIR)   # CosyVoice busca 'pretrained_models' relativo al CWD
OUTPUT_DIR.mkdir(exist_ok=True)

import torch
import torchaudio

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

TEXTS = [
    ("corto",
     "Buenos dias! En el dia de hoy realizamos una prueba de sintesis de voz. Espero que todo vaya bien contigo."),
    ("medio",
     "La inteligencia artificial ha transformado la forma en que interactuamos con la tecnologia. "
     "Hoy evaluamos la calidad de sintesis de voz con este modelo de clonacion avanzado en espanol."),
    ("largo",
     "La tecnologia de clonacion de voz ha avanzado enormemente en los ultimos anos, "
     "permitiendo sintetizar cualquier voz con solo unos segundos de audio de referencia. "
     "Estos modelos logran capturar el timbre, la entonacion y las caracteristicas "
     "prosodicas del hablante original con resultados muy naturales y expresivos."),
]

SEP  = "-" * 60
SEP2 = "=" * 60

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(SEP2)
    print("  CosyVoice3 (Fun-CosyVoice3-0.5B) — Test local")
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

    print("\nCargando CosyVoice3...")
    t0 = time.time()
    from cosyvoice.cli.cosyvoice import AutoModel
    cosyvoice = AutoModel(
        model_dir="pretrained_models/Fun-CosyVoice3-0.5B",
        fp16=False,
    )
    # Blackwell fix: LLM debe ser float32
    cosyvoice.model.llm = cosyvoice.model.llm.float()
    t_load = time.time() - t0
    vram_l = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
    print(f"  OK en {t_load:.1f}s | LLM dtype: {next(cosyvoice.model.llm.parameters()).dtype} | VRAM: {vram_l:.0f} MB")
    print(SEP)

    results = []
    for nombre, texto in TEXTS:
        print(f"\n  [{nombre.upper()}] {len(texto)} chars")

        t0 = time.time()
        audio_chunks = list(cosyvoice.inference_zero_shot(
            texto,
            REF_TEXT,
            str(REF_AUDIO),
            stream=False,
        ))
        t_gen = time.time() - t0

        if not audio_chunks:
            print("  ERROR: no se generó audio")
            continue

        audio_tensor = audio_chunks[0]["tts_speech"]
        wav_out      = audio_tensor.clamp(-1.0, 1.0)
        out          = OUTPUT_DIR / f"cosyvoice_{nombre}.wav"
        torchaudio.save(str(out), wav_out, cosyvoice.sample_rate,
                        encoding="PCM_S", bits_per_sample=16)

        dur  = audio_tensor.shape[-1] / cosyvoice.sample_rate
        rtf  = t_gen / dur if dur > 0 else 0
        vram = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
        tag  = "FAST" if rtf < 1.0 else "SLOW"
        print(f"  T {t_gen:.2f}s | Audio {dur:.2f}s | RTF {rtf:.3f} [{tag}] | VRAM {vram:.0f} MB")
        print(f"  Guardado: {out}")
        results.append((nombre, dur, t_gen, rtf, vram))

    print(f"\n{SEP2}")
    print("  RESUMEN")
    print(SEP2)
    if results:
        rtfs = [r[3] for r in results]
        print(f"  RTF avg   : {sum(rtfs)/len(rtfs):.3f}")
        print(f"  VRAM peak : {torch.cuda.max_memory_allocated()/1024**2:.0f} MB")
    print(f"  Salidas   : {OUTPUT_DIR}")
    print(SEP2)

if __name__ == "__main__":
    main()
