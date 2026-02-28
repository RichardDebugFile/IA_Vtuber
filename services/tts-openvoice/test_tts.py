"""
Test de OpenVoice V2 — repo local
Venv: services/tts-openvoice/venv
Referencia: casiopy-V2/CasiopyVoz-15s.wav
"""
import os, sys, time
from pathlib import Path

# Paths locales
SERVICE_DIR    = Path(__file__).parent
REPO_DIR       = SERVICE_DIR / "repo"
CKPT_DIR       = REPO_DIR / "checkpoints_v2"
OUTPUT_DIR     = SERVICE_DIR / "outputs"
REF_AUDIO      = SERVICE_DIR.parent.parent / "casiopy-V2" / "CasiopyVoz-15s.wav"

sys.path.insert(0, str(REPO_DIR))
os.chdir(REPO_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

import torch
import soundfile as sf

# Blackwell fix
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

TEXTOS = {
    "corto": "Hola, como estas? Espero que todo vaya bien.",
    "medio": (
        "Buenos dias. En el dia de hoy vamos a realizar una prueba de generacion "
        "de voz con un texto de longitud media. Este tipo de textos son comunes "
        "en aplicaciones de asistentes virtuales."
    ),
    "largo": (
        "La tecnologia de clonacion de voz ha avanzado enormemente en los ultimos anos, "
        "permitiendo sintetizar cualquier voz con solo unos segundos de audio de referencia. "
        "Estos modelos basados en transformers logran capturar el timbre, la entonacion "
        "y las caracteristicas prosodicas del hablante original."
    ),
}

SEP  = "-" * 65
SEP2 = "=" * 65

def get_dur(path):
    data, sr = sf.read(path)
    return len(data) / sr

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(SEP2)
    print("  OpenVoice V2 -- Test local")
    print(SEP2)
    print(f"  Device  : {device}")
    if torch.cuda.is_available():
        print(f"  GPU     : {torch.cuda.get_device_name(0)}")
        torch.cuda.reset_peak_memory_stats()
    print(f"  Ref     : {REF_AUDIO}")
    if not REF_AUDIO.exists():
        print(f"  ERROR: Audio de referencia no encontrado: {REF_AUDIO}")
        sys.exit(1)
    print(SEP)

    # Cargar modelos
    print("\n[1/3] Cargando ToneColorConverter...")
    t0 = time.time()
    from openvoice import se_extractor
    from openvoice.api import ToneColorConverter
    conv_cfg  = str(CKPT_DIR / "converter" / "config.json")
    conv_ckpt = str(CKPT_DIR / "converter" / "checkpoint.pth")
    tone_conv = ToneColorConverter(conv_cfg, device=device)
    tone_conv.load_ckpt(conv_ckpt)
    print(f"  OK en {time.time()-t0:.1f}s | VRAM: {torch.cuda.memory_allocated()/1024**2:.0f} MB")

    print("\n[2/3] Cargando MeloTTS (ES)...")
    t0 = time.time()
    from melo.api import TTS as MeloTTS
    model   = MeloTTS(language="ES", device=device)
    spk_ids = model.hps.data.spk2id
    sid     = list(spk_ids.values())[0]
    spk_key = list(spk_ids.keys())[0].lower().replace("_", "-")
    print(f"  OK en {time.time()-t0:.1f}s | VRAM: {torch.cuda.memory_allocated()/1024**2:.0f} MB | spk={spk_key}")

    print("\n[3/3] Extrayendo speaker embedding de referencia...")
    ses_dir   = CKPT_DIR / "base_speakers" / "ses"
    se_src    = torch.load(ses_dir / f"{spk_key}.pth", map_location=device, weights_only=False)
    se_tgt, _ = se_extractor.get_se(str(REF_AUDIO), tone_conv, vad=True)
    print(f"  OK")
    print(SEP)

    # Generación
    results  = []
    tmp_path = str(OUTPUT_DIR / "_tmp.wav")
    for nombre, texto in TEXTOS.items():
        print(f"\n  [{nombre.upper()}] {len(texto)} chars")
        t_a = time.time()
        model.tts_to_file(texto, sid, tmp_path, speed=1.0)
        t_melo = time.time() - t_a

        out = str(OUTPUT_DIR / f"openvoice_{nombre}.wav")
        t_b = time.time()
        tone_conv.convert(audio_src_path=tmp_path, src_se=se_src,
                          tgt_se=se_tgt, output_path=out, message="@OV2")
        t_conv = time.time() - t_b

        dur    = get_dur(out)
        t_tot  = t_melo + t_conv
        rtf    = t_tot / dur if dur > 0 else 0
        vram   = torch.cuda.memory_allocated() / 1024**2
        estado = "FAST" if rtf < 1.0 else "SLOW"
        print(f"  MeloTTS {t_melo:.2f}s | Conv {t_conv:.2f}s | "
              f"Total {t_tot:.2f}s | Audio {dur:.2f}s | RTF {rtf:.3f} [{estado}]")
        print(f"  VRAM {vram:.0f} MB | Guardado: {out}")
        results.append((nombre, dur, t_tot, rtf, vram))

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    print(f"\n{SEP2}")
    print("  RESUMEN")
    print(SEP2)
    rtfs = [r[3] for r in results]
    print(f"  RTF avg: {sum(rtfs)/len(rtfs):.3f} | VRAM peak: {torch.cuda.max_memory_allocated()/1024**2:.0f} MB")
    print(f"  Salidas: {OUTPUT_DIR}")
    print(SEP2)

if __name__ == "__main__":
    main()
