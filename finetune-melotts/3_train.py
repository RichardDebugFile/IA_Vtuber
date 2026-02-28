"""
Paso 3 — Lanzar entrenamiento fine-tune de MeloTTS
===================================================
Arranca desde el checkpoint ES de MeloTTS (ya descargado en cache HF) y
fine-tunea la voz "casiopy" usando torchrun con 1 GPU.

El entrenamiento guarda checkpoints en:
  logs/casiopy/G_*.pth   — generator (el modelo que usaremos)
  logs/casiopy/D_*.pth   — discriminator
  logs/casiopy/DUR_*.pth — duration discriminator

Progreso en TensorBoard:
  tensorboard --logdir logs/casiopy

Uso:
  python 3_train.py [--resume] [--batch-size N] [--epochs N] [--port N]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
FINETUNE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = FINETUNE_DIR.parent
DATA_DIR     = FINETUNE_DIR / "data"
LOGS_DIR     = FINETUNE_DIR / "logs" / "casiopy"
CONFIG_PATH  = DATA_DIR / "config.json"

MELO_VENV    = PROJECT_ROOT / "services" / "tts-openvoice" / "venv"
PYTHON_EXE   = MELO_VENV / "Scripts" / "python.exe"

HF_CACHE_ES  = (
    Path.home() / ".cache" / "huggingface" / "hub"
    / "models--myshell-ai--MeloTTS-Spanish" / "snapshots"
)


def _find_es_checkpoint() -> Path | None:
    """Localiza el checkpoint.pth de MeloTTS-Spanish en la cache HF."""
    if HF_CACHE_ES.exists():
        for snapshot in sorted(HF_CACHE_ES.iterdir(), reverse=True):
            ckpt = snapshot / "checkpoint.pth"
            if ckpt.exists():
                return ckpt
    return None


def _latest_checkpoint(pattern: str) -> Path | None:
    import glob
    files = sorted(glob.glob(str(LOGS_DIR / pattern)))
    return Path(files[-1]) if files else None


def main():
    parser = argparse.ArgumentParser(description="Lanza fine-tuning de MeloTTS")
    parser.add_argument("--resume",     action="store_true",
                        help="Reanudar desde el ultimo checkpoint guardado")
    parser.add_argument("--batch-size", type=int, default=0,
                        help="Sobreescribir batch_size del config (0=usar config)")
    parser.add_argument("--epochs",     type=int, default=0,
                        help="Sobreescribir epochs del config (0=usar config)")
    parser.add_argument("--port",       type=int, default=10001,
                        help="Puerto para torchrun DDP (default: 10001)")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Solo mostrar el comando, no ejecutar")
    args = parser.parse_args()

    # ── Verificar prerequisitos ───────────────────────────────────────────
    if not CONFIG_PATH.exists():
        print(f"[ERROR] No se encontró {CONFIG_PATH}")
        print("        Ejecuta primero: python 2_preprocess.py")
        sys.exit(1)

    if not PYTHON_EXE.exists():
        print(f"[ERROR] Python del venv no encontrado: {PYTHON_EXE}")
        sys.exit(1)

    # ── Encontrar checkpoint ES para pretrain ────────────────────────────
    es_ckpt = _find_es_checkpoint()
    if es_ckpt is None:
        print("[WARN] Checkpoint ES no encontrado en cache HF.")
        print("       Se usarán los pesos pretrained genéricos (G.pth/D.pth/DUR.pth).")
        print("       Para mejores resultados, ejecuta primero el servicio tts-openvoice")
        print("       para que descargue el checkpoint ES.")
        pretrain_g_arg = []
    else:
        print(f"[3_train] Checkpoint ES encontrado: {es_ckpt}")
        pretrain_g_arg = ["--pretrain_G", str(es_ckpt)]

    # ── Modificar config si se pasaron overrides ─────────────────────────
    if args.batch_size > 0 or args.epochs > 0:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        if args.batch_size > 0:
            cfg["train"]["batch_size"] = args.batch_size
            print(f"[3_train] Override batch_size={args.batch_size}")
        if args.epochs > 0:
            cfg["train"]["epochs"] = args.epochs
            print(f"[3_train] Override epochs={args.epochs}")
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    # ── Verificar si ya hay checkpoints (resume) ─────────────────────────
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Copiar config al directorio de logs (requerido por utils.get_hparams)
    import shutil
    shutil.copy(CONFIG_PATH, LOGS_DIR / "config.json")

    existing_g = _latest_checkpoint("G_*.pth")
    if existing_g and not args.resume:
        print(f"\n[WARN] Se encontró checkpoint existente: {existing_g.name}")
        print("       Usa --resume para continuar desde ahí, o borra logs/casiopy/ para empezar de cero.")
        answer = input("       ¿Continuar desde el checkpoint existente? [s/N]: ").strip().lower()
        if answer != "s":
            print("Abortando. Usa --resume para reanudar o borra logs/casiopy/ para empezar de cero.")
            sys.exit(0)
        args.resume = True

    if args.resume and existing_g:
        print(f"[3_train] Reanudando desde: {existing_g.name}")
        pretrain_g_arg = []  # al reanudar, carga desde logs/casiopy/G_*.pth automáticamente

    # ── Construir comando ─────────────────────────────────────────────────
    # torchrun lanza el entrenamiento distribuido con 1 GPU
    cmd = [
        str(PYTHON_EXE), "-m", "torch.distributed.run",  # torchrun como módulo Python
        "--nproc_per_node=1",
        f"--master_port={args.port}",
        "-m", "melo.train",
        "-m", "casiopy",                    # model name -> logs/casiopy/
        "-c", str(CONFIG_PATH),
    ] + pretrain_g_arg

    print("\n[3_train] Comando de entrenamiento:")
    print("  " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
    print(f"\n[3_train] Logs y checkpoints en: {LOGS_DIR}")
    print("[3_train] Monitorear con TensorBoard:")
    print(f"  tensorboard --logdir \"{FINETUNE_DIR / 'logs'}\"")
    print()

    if args.dry_run:
        print("[dry-run] No se ejecutó el entrenamiento.")
        return

    # ── Ejecutar ──────────────────────────────────────────────────────────
    env = os.environ.copy()
    # Asegurar que el venv está en el PATH
    env["PATH"] = str(MELO_VENV / "Scripts") + os.pathsep + env.get("PATH", "")
    # Necesario para torchrun con 1 GPU
    env.setdefault("LOCAL_RANK", "0")
    # Windows: PyTorch puede compilarse sin libuv; desactivarlo evita DistStoreError
    env["USE_LIBUV"] = "0"
    # Windows: forzar UTF-8 en todos los open() — melo/utils.py lee config.json sin encoding
    env["PYTHONUTF8"] = "1"
    # MeloTTS train.py usa bare imports (commons, utils, models, text...)
    # que asumen que melo/ está como raíz en el path. PYTHONPATH lo propaga
    # a los procesos hijo de torchrun donde sys.path no es heredado.
    melo_pkg = str(MELO_VENV / "Lib" / "site-packages" / "melo")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = melo_pkg + (os.pathsep + existing_pp if existing_pp else "")

    print("[3_train] Iniciando entrenamiento... (Ctrl+C para detener y guardar checkpoint)")
    print("=" * 60)

    result = subprocess.run(cmd, env=env, cwd=str(FINETUNE_DIR))

    if result.returncode == 0:
        print("\n[3_train] Entrenamiento completado.")
        best_g = _latest_checkpoint("G_*.pth")
        if best_g:
            print(f"[3_train] Ultimo checkpoint: {best_g}")
            print(f"\n-> Siguiente paso: python 4_test.py")
    else:
        print(f"\n[ERROR] El entrenamiento terminó con codigo {result.returncode}")
        print("  Posibles causas:")
        print("  - OOM: reduce batch_size con --batch-size 4")
        print("  - Config erronea: revisa data/config.json")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
