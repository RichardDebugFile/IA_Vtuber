"""
Paso 1 — Preparar dataset para fine-tuning de MeloTTS
======================================================
Lee  : ../dataset/metadata.csv   (formato: filename|texto)
       ../dataset/wavs/           (WAV 24kHz mono)

Genera:
  data/wavs_44k/   — audio resampleado a 44100 Hz (requerido por MeloTTS ES)
  data/metadata.list — lista para preprocess_text.py
                       formato: ruta_absoluta|casiopy|ES|texto

Uso:
  python 1_prepare_dataset.py [--limit N] [--workers N]
"""

import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── Rutas base ──────────────────────────────────────────────────────────────
FINETUNE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = FINETUNE_DIR.parent
DATASET_DIR  = PROJECT_ROOT / "dataset"
WAVS_SRC     = DATASET_DIR / "wavs"
METADATA_CSV = DATASET_DIR / "metadata.csv"

DATA_DIR     = FINETUNE_DIR / "data"
WAVS_44K     = DATA_DIR / "wavs_44k"
METADATA_OUT = DATA_DIR / "metadata.list"

TARGET_SR    = 44100
SPEAKER_NAME = "casiopy"
LANGUAGE     = "ES"


def _check_deps():
    missing = []
    try:
        import soundfile  # noqa
    except ImportError:
        missing.append("soundfile")
    try:
        import numpy  # noqa
    except ImportError:
        missing.append("numpy")
    try:
        from scipy.signal import resample_poly  # noqa
    except ImportError:
        missing.append("scipy")
    if missing:
        print(f"[ERROR] Dependencias faltantes: {', '.join(missing)}")
        print("        Activa el venv de tts-openvoice o instala con pip:")
        print(f"        pip install {' '.join(missing)}")
        sys.exit(1)


def resample_wav(src_path: Path, dst_path: Path, target_sr: int) -> bool:
    """Resamplea un WAV a target_sr. Devuelve True si lo procesó, False si lo saltó."""
    import soundfile as sf
    import numpy as np
    from math import gcd
    from scipy.signal import resample_poly

    if dst_path.exists():
        return False  # ya procesado — resume support

    audio, src_sr = sf.read(str(src_path))

    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # forzar mono

    if src_sr != target_sr:
        g = gcd(src_sr, target_sr)
        up   = target_sr // g
        down = src_sr    // g
        audio = resample_poly(audio, up, down).astype(np.float32)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst_path), audio, target_sr, subtype="PCM_16")
    return True


def main():
    parser = argparse.ArgumentParser(description="Prepara dataset para MeloTTS fine-tune")
    parser.add_argument("--limit",   type=int, default=0,  help="Limitar a N muestras (0=todas)")
    parser.add_argument("--workers", type=int, default=4,  help="Hilos paralelos para resampleo")
    args = parser.parse_args()

    _check_deps()

    # ── Verificar rutas ───────────────────────────────────────────────────
    if not METADATA_CSV.exists():
        print(f"[ERROR] No se encontró metadata.csv en {METADATA_CSV}")
        sys.exit(1)
    if not WAVS_SRC.exists():
        print(f"[ERROR] No se encontró directorio de wavs en {WAVS_SRC}")
        sys.exit(1)

    DATA_DIR.mkdir(exist_ok=True)
    WAVS_44K.mkdir(exist_ok=True)

    # ── Leer metadata.csv ─────────────────────────────────────────────────
    entries = []
    with open(METADATA_CSV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 1)
            if len(parts) != 2:
                continue
            filename, text = parts
            # filename puede ser con o sin extensión
            if not filename.endswith(".wav"):
                filename = filename + ".wav"
            src = WAVS_SRC / filename
            if not src.exists():
                print(f"[WARN] Audio no encontrado, saltando: {src}")
                continue
            entries.append((src, text.strip()))

    if args.limit > 0:
        entries = entries[: args.limit]

    total = len(entries)
    print(f"[1_prepare] {total} muestras encontradas en metadata.csv")
    print(f"[1_prepare] Resampleando 24000 Hz -> {TARGET_SR} Hz con {args.workers} hilos...")

    # ── Resamplear audio ──────────────────────────────────────────────────
    processed = 0
    skipped   = 0
    errors    = 0

    def _job(item):
        src, _ = item
        dst = WAVS_44K / src.name
        try:
            did_work = resample_wav(src, dst, TARGET_SR)
            return "done" if did_work else "skip"
        except Exception as e:
            return f"error:{e}"

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_job, item): item for item in entries}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result == "done":
                processed += 1
            elif result == "skip":
                skipped += 1
            else:
                errors += 1
                src, _ = futures[future]
                print(f"[WARN] Error en {src.name}: {result}")
            if i % 200 == 0 or i == total:
                print(f"  {i}/{total}  procesados={processed}  saltados(ya existian)={skipped}  errores={errors}")

    # ── Generar metadata.list ─────────────────────────────────────────────
    print(f"\n[1_prepare] Generando {METADATA_OUT} ...")
    written = 0
    with open(METADATA_OUT, "w", encoding="utf-8") as f:
        for src, text in entries:
            dst = WAVS_44K / src.name
            if dst.exists():
                abs_path = str(dst.resolve())
                f.write(f"{abs_path}|{SPEAKER_NAME}|{LANGUAGE}|{text}\n")
                written += 1

    print(f"[1_prepare] Listo. {written} entradas escritas en metadata.list")
    print(f"[1_prepare] Audios en: {WAVS_44K}")
    print(f"\n-> Siguiente paso: python 2_preprocess.py")


if __name__ == "__main__":
    main()
