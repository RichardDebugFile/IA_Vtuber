"""
Paso 4 — Probar el modelo fine-tuneado
======================================
Carga el ultimo checkpoint de logs/casiopy/ y genera audios de prueba.
Compara con el modelo ES base para ver la diferencia.

Genera archivos en output/:
  test_casiopy_XX.wav   — audio con el modelo fine-tuneado (voz casiopy)
  test_base_es_XX.wav   — audio con el modelo ES original (referencia)

Uso:
  python 4_test.py [--text "Texto de prueba"] [--checkpoint G_NNNNN.pth]
"""

import argparse
import sys
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
FINETUNE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = FINETUNE_DIR.parent
LOGS_DIR     = FINETUNE_DIR / "logs" / "casiopy"
OUTPUT_DIR   = FINETUNE_DIR / "output"
DATA_DIR     = FINETUNE_DIR / "data"

MELO_VENV    = PROJECT_ROOT / "services" / "tts-openvoice" / "venv"
MELO_SITE    = MELO_VENV / "Lib" / "site-packages"

# Frases de prueba variadas para evaluar la voz
DEFAULT_TEXTS = [
    "Hola a todos, soy casiopy y bienvenidos al stream de hoy.",
    "Eso estuvo muy bien, la verdad que me sorprendiste.",
    "No puedo creer lo que acaba de pasar, esto es increíble.",
    "Vamos a intentarlo una vez más, estoy segura de que podemos lograrlo.",
    "Muchas gracias por acompañarme hoy, significa mucho para mí.",
]


def _add_melo_to_path():
    site = str(MELO_SITE)
    if site not in sys.path:
        sys.path.insert(0, site)
    try:
        import melo  # noqa
        return True
    except ImportError:
        return False


def _find_latest_checkpoint() -> Path | None:
    import glob
    files = sorted(glob.glob(str(LOGS_DIR / "G_*.pth")))
    return Path(files[-1]) if files else None


def main():
    parser = argparse.ArgumentParser(description="Prueba el modelo fine-tuneado")
    parser.add_argument("--text",       type=str, default=None,
                        help="Texto personalizado a sintetizar")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Nombre del checkpoint a usar (ej: G_10000.pth). Default: ultimo")
    parser.add_argument("--no-compare", action="store_true",
                        help="No generar audio de comparacion con ES base")
    parser.add_argument("--speed",      type=float, default=1.0,
                        help="Velocidad de sintesis (default: 1.0)")
    args = parser.parse_args()

    if not _add_melo_to_path():
        print(f"[ERROR] No se pudo importar melo desde {MELO_SITE}")
        sys.exit(1)

    # ── Encontrar checkpoint ──────────────────────────────────────────────
    if args.checkpoint:
        ckpt_path = LOGS_DIR / args.checkpoint
    else:
        ckpt_path = _find_latest_checkpoint()

    if ckpt_path is None or not ckpt_path.exists():
        print(f"[ERROR] No se encontró checkpoint en {LOGS_DIR}")
        print("        Ejecuta primero: python 3_train.py")
        sys.exit(1)

    config_path = LOGS_DIR / "config.json"
    if not config_path.exists():
        print(f"[ERROR] No se encontró config en {config_path}")
        sys.exit(1)

    print(f"[4_test] Checkpoint: {ckpt_path.name}")
    print(f"[4_test] Config:     {config_path}")

    # ── Determinar textos ─────────────────────────────────────────────────
    texts = [args.text] if args.text else DEFAULT_TEXTS

    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Cargar modelo fine-tuneado ────────────────────────────────────────
    print("\n[4_test] Cargando modelo fine-tuneado (casiopy)...")
    from melo.api import TTS
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[4_test] Device: {device}")

    # Cargar con config personalizada y checkpoint fine-tuneado
    model_ft = TTS(
        language="ES",
        device=device,
        use_hf=False,
        config_path=str(config_path),
        ckpt_path=str(ckpt_path),
    )
    spk_ids_ft = model_ft.hps.data.spk2id
    print(f"[4_test] Speakers disponibles: {spk_ids_ft}")

    # Usar casiopy si está disponible, si no, ES
    if "casiopy" in spk_ids_ft:
        speaker_ft = spk_ids_ft["casiopy"]
        print(f"[4_test] Usando speaker 'casiopy' (ID={speaker_ft})")
    else:
        speaker_ft = spk_ids_ft["ES"]
        print(f"[4_test] Speaker 'casiopy' no encontrado, usando 'ES' (ID={speaker_ft})")

    # ── Generar audio con modelo fine-tuneado ─────────────────────────────
    print(f"\n[4_test] Generando {len(texts)} audio(s) con modelo casiopy...")
    for i, text in enumerate(texts, 1):
        out_path = str(OUTPUT_DIR / f"test_casiopy_{i:02d}.wav")
        print(f"  [{i}/{len(texts)}] {text[:60]}...")
        model_ft.tts_to_file(text, speaker_ft, out_path, speed=args.speed)
        print(f"         -> {out_path}")

    # ── Generar comparación con ES base ───────────────────────────────────
    if not args.no_compare:
        print(f"\n[4_test] Generando comparacion con ES base...")
        model_base = TTS(language="ES", device=device)
        spk_base   = model_base.hps.data.spk2id["ES"]

        for i, text in enumerate(texts, 1):
            out_path = str(OUTPUT_DIR / f"test_base_es_{i:02d}.wav")
            print(f"  [{i}/{len(texts)}] (base ES) {text[:60]}...")
            model_base.tts_to_file(text, spk_base, out_path, speed=args.speed)
            print(f"         -> {out_path}")

    # ── Resumen ───────────────────────────────────────────────────────────
    print(f"\n[4_test] Audios generados en: {OUTPUT_DIR}")
    print("[4_test] Escucha y compara:")
    print("  test_casiopy_*.wav  — modelo fine-tuneado")
    if not args.no_compare:
        print("  test_base_es_*.wav  — ES original (referencia)")
    print("\n[4_test] Si la voz suena bien:")
    print("  -> Siguiente paso: integrar el checkpoint en services/tts-openvoice/")
    print(f"     Checkpoint a copiar: {ckpt_path}")
    print(f"     Config a copiar:     {config_path}")


if __name__ == "__main__":
    main()
