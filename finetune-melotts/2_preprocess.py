"""
Paso 2 — Fonemización y generación de config de entrenamiento
=============================================================
Lee  : data/metadata.list  (generado por 1_prepare_dataset.py)

Genera:
  data/metadata.list.cleaned — lista fonemizada (phones, tones, word2ph)
  data/train.list            — split de entrenamiento
  data/val.list              — split de validación (8 muestras)
  data/config.json           — config de entrenamiento (basado en ES + fine-tune params)

NOTA: MeloTTS ES tiene disable_bert=true, por lo que NO se generan
      embeddings BERT. El preprocesado es solo fonemización con espanol IPA.

Uso:
  python 2_preprocess.py [--val-per-spk N]
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
FINETUNE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = FINETUNE_DIR.parent
DATA_DIR     = FINETUNE_DIR / "data"
METADATA_IN  = DATA_DIR / "metadata.list"
CONFIG_OUT   = DATA_DIR / "config.json"

# ── Venv de tts-openvoice (donde está melo instalado) ────────────────────────
MELO_VENV    = PROJECT_ROOT / "services" / "tts-openvoice" / "venv"
MELO_SITE    = MELO_VENV / "Lib" / "site-packages"

# ── Config base de MeloTTS ES (descargado de HF) ─────────────────────────────
HF_CACHE_ES = (
    Path.home() / ".cache" / "huggingface" / "hub"
    / "models--myshell-ai--MeloTTS-Spanish" / "snapshots"
)

# Parámetros de entrenamiento para fine-tune
FINETUNE_TRAIN_PARAMS = {
    "log_interval":   200,
    "eval_interval":  500,    # Checkpoint cada ~500 pasos (~2-3 min con batch=16)
    "seed":           1234,
    "epochs":         200,
    "learning_rate":  2e-4,       # LR estándar de MeloTTS
    "betas":          [0.8, 0.99],
    "eps":            1e-9,
    "batch_size":     16,          # 16 = ~2-3h total / 6 = ~5-8h. Bajar a 8 si hay OOM.
    "fp16_run":       False,
    "lr_decay":       0.999875,
    "segment_size":   16384,
    "init_lr_ratio":  1,
    "warmup_epochs":  0,
    "c_mel":          45,
    "c_kl":           1.0,
    "keep_ckpts":     5,
}


def _add_melo_to_path():
    """Añade el site-packages del venv de tts-openvoice al path.

    MeloTTS usa imports bare como `from text import cleaner` que asumen
    que el directorio melo/ está en sys.path como raíz.
    Sin esto, `import text` falla con ModuleNotFoundError.
    """
    site = str(MELO_SITE)
    melo_pkg = str(MELO_SITE / "melo")  # para que 'from text import ...' funcione
    if site not in sys.path:
        sys.path.insert(0, site)
    if melo_pkg not in sys.path:
        sys.path.insert(0, melo_pkg)
    try:
        import melo  # noqa
        return True
    except ImportError:
        return False


def _find_hf_config() -> Path | None:
    """Busca el config.json de MeloTTS-Spanish en la cache de HuggingFace."""
    if HF_CACHE_ES.exists():
        for snapshot in sorted(HF_CACHE_ES.iterdir()):
            cfg = snapshot / "config.json"
            if cfg.exists():
                return cfg
    return None


def _build_training_config(base_config: dict) -> dict:
    """Construye el config.json de entrenamiento partiendo del config ES base."""
    cfg = json.loads(json.dumps(base_config))  # deep copy

    # Parámetros de entrenamiento
    cfg["train"] = {**cfg.get("train", {}), **FINETUNE_TRAIN_PARAMS}

    # Rutas de datos
    cfg["data"]["training_files"]   = str(DATA_DIR / "train.list")
    cfg["data"]["validation_files"] = str(DATA_DIR / "val.list")

    # Añadir casiopy como speaker ID 1 (ES permanece en 0)
    cfg["data"]["spk2id"] = {"ES": 0, "casiopy": 1}
    cfg["data"]["n_speakers"] = 256  # mantener igual que ES base

    # Campos estándar VITS que el config base ES omite pero data_utils.py/train.py requiere
    cfg["data"].setdefault("max_wav_value",  32768.0)
    cfg["data"].setdefault("win_length",     cfg["data"].get("filter_length", 2048))
    cfg["data"].setdefault("mel_fmin",       0.0)
    cfg["data"].setdefault("mel_fmax",       None)
    cfg["data"].setdefault("n_mel_channels", 80)

    # num_languages debe coincidir con len(language_id_map) en melo/text/symbols.py (=8)
    # para que api.py y train.py creen el mismo tamaño de embedding
    cfg["num_languages"] = 8

    return cfg


def main():
    parser = argparse.ArgumentParser(description="Fonemiza dataset y genera config de entrenamiento")
    parser.add_argument("--val-per-spk", type=int, default=8,
                        help="Muestras de validacion por speaker (default: 8)")
    args = parser.parse_args()

    # ── Verificar prerequisitos ───────────────────────────────────────────
    if not METADATA_IN.exists():
        print(f"[ERROR] No se encontró {METADATA_IN}")
        print("        Ejecuta primero: python 1_prepare_dataset.py")
        sys.exit(1)

    if not _add_melo_to_path():
        print(f"[ERROR] No se pudo importar melo desde {MELO_SITE}")
        print("        Asegúrate de que el servicio tts-openvoice tiene su venv configurado.")
        sys.exit(1)

    # ── Cargar config base de MeloTTS ES ─────────────────────────────────
    base_cfg_path = _find_hf_config()
    if base_cfg_path is None:
        print("[WARN] Config ES no encontrada en cache HF, descargando...")
        from melo.download_utils import load_or_download_config
        hps = load_or_download_config("ES")
        # Reconstruir como dict desde hps
        from melo import utils as melo_utils
        from huggingface_hub import hf_hub_download
        base_cfg_path = Path(hf_hub_download(
            repo_id="myshell-ai/MeloTTS-Spanish", filename="config.json"
        ))

    with open(base_cfg_path, encoding="utf-8") as f:
        base_config = json.load(f)

    print(f"[2_preprocess] Config base ES cargada: {base_cfg_path}")
    print(f"[2_preprocess] sampling_rate={base_config['data']['sampling_rate']} Hz  "
          f"disable_bert={base_config['data'].get('disable_bert', False)}")

    # ── Fonemizar metadata.list ───────────────────────────────────────────
    from melo.text.cleaner import clean_text_bert
    from melo.text.symbols import symbols

    metadata_lines = [l.strip() for l in open(METADATA_IN, encoding="utf-8") if l.strip()]
    total = len(metadata_lines)
    print(f"[2_preprocess] Fonemizando {total} muestras (disable_bert=True -> rapido)...")

    cleaned_path = DATA_DIR / "metadata.list.cleaned"
    new_symbols  = []
    ok_lines     = []
    errors       = 0

    with open(cleaned_path, "w", encoding="utf-8") as out:
        for i, line in enumerate(metadata_lines, 1):
            try:
                utt, spk, lang, text = line.split("|", 3)
                norm_text, phones, tones, word2ph, bert = clean_text_bert(
                    text, lang, device="cuda:0"
                )
                for ph in phones:
                    if ph not in symbols and ph not in new_symbols:
                        new_symbols.append(ph)

                assert len(phones) == len(tones)
                assert len(phones) == sum(word2ph)

                cleaned_line = "{}|{}|{}|{}|{}|{}|{}\n".format(
                    utt, spk, lang, norm_text,
                    " ".join(phones),
                    " ".join(str(t) for t in tones),
                    " ".join(str(w) for w in word2ph),
                )
                out.write(cleaned_line)
                ok_lines.append(cleaned_line)

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  [WARN] Error en linea {i}: {e!r}  ->  {line[:80]}")

            if i % 200 == 0 or i == total:
                print(f"  {i}/{total}  ok={len(ok_lines)}  errores={errors}")

    print(f"[2_preprocess] Fonemizacion completa: {len(ok_lines)} ok / {errors} errores")

    if len(ok_lines) == 0:
        print("[ERROR] 0 muestras fonemizadas correctamente. Revisa los errores anteriores.")
        print("        Causa probable: imports internos de MeloTTS no resueltos.")
        sys.exit(1)

    if new_symbols:
        print(f"[WARN] Simbolos nuevos no vistos antes: {new_symbols}")

    # ── Split train / val ─────────────────────────────────────────────────
    from random import Random
    rng = Random(42)
    rng.shuffle(ok_lines)

    val_count  = min(args.val_per_spk, max(1, len(ok_lines) // 50))
    val_lines  = ok_lines[:val_count]
    train_lines = ok_lines[val_count:]

    train_path = DATA_DIR / "train.list"
    val_path   = DATA_DIR / "val.list"

    with open(train_path, "w", encoding="utf-8") as f:
        f.writelines(train_lines)
    with open(val_path, "w", encoding="utf-8") as f:
        f.writelines(val_lines)

    print(f"[2_preprocess] Split: {len(train_lines)} train / {len(val_lines)} val")

    # ── Generar config.json de entrenamiento ──────────────────────────────
    train_config = _build_training_config(base_config)
    with open(CONFIG_OUT, "w", encoding="utf-8") as f:
        json.dump(train_config, f, indent=2, ensure_ascii=False)

    print(f"[2_preprocess] Config de entrenamiento guardada: {CONFIG_OUT}")
    print(f"  batch_size={train_config['train']['batch_size']}  "
          f"lr={train_config['train']['learning_rate']}  "
          f"epochs={train_config['train']['epochs']}")
    print(f"\n-> Siguiente paso: python 3_train.py")


if __name__ == "__main__":
    main()
