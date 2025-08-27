# services/tts/src/pyinject/sitecustomize.py
import os

def _log(msg: str) -> None:
    if os.environ.get("FISH_CUDA_VERBOSE"):
        print(f"[cuda-guard] {msg}", flush=True)

def _normalize_alloc_conf(env: dict) -> None:
    conf = env.get("PYTORCH_CUDA_ALLOC_CONF", "")
    if "max_split_size_mb=" in conf or ";" in conf:
        conf2 = conf.replace("=", ":").replace(";", ",")
        env["PYTORCH_CUDA_ALLOC_CONF"] = conf2
        _log(f"normalized PYTORCH_CUDA_ALLOC_CONF -> {conf2}")

def _set_limit() -> None:
    # Normaliza el alloc conf (si vino en formato viejo)
    _normalize_alloc_conf(os.environ)

    try:
        import torch  # noqa: F401
    except Exception as e:
        _log(f"torch import failed: {e}")
        return

    import torch

    if not torch.cuda.is_available():
        _log("CUDA not available; skipping")
        return

    dev = int(os.environ.get("FISH_CUDA_DEVICE", "0"))
    try:
        torch.cuda.set_device(dev)
    except Exception as e:
        _log(f"set_device({dev}) failed: {e}")
        return

    props = torch.cuda.get_device_properties(dev)
    total = float(props.total_memory)  # bytes

    # Prioridad: FISH_CUDA_MAX_GB -> FISH_CUDA_FRACTION
    frac = None
    max_gb_str = os.environ.get("FISH_CUDA_MAX_GB", "").strip()
    if max_gb_str:
        try:
            max_gb = float(max_gb_str)
            frac = (max_gb * (1024.0 ** 3)) / total
        except Exception as e:
            _log(f"bad FISH_CUDA_MAX_GB='{max_gb_str}': {e}")

    if frac is None:
        frac_str = os.environ.get("FISH_CUDA_FRACTION", "").strip()
        if frac_str:
            try:
                frac = float(frac_str)
            except Exception as e:
                _log(f"bad FISH_CUDA_FRACTION='{frac_str}': {e}")

    if frac is None:
        # sin limites explícitos, no tocamos nada
        _log("no limit envs set; leaving default allocator config")
        return

    # Clampeamos a [0.05, 0.95] para evitar edge-cases
    frac = max(0.05, min(0.95, frac))

    try:
        torch.cuda.set_per_process_memory_fraction(frac, device=dev)
        _log(f"total={total/1024**3:.2f}GB  limit_frac={frac:.3f}  target≈{frac*total/1024**3:.2f}GB (device {dev})")
    except Exception as e:
        _log(f"set_per_process_memory_fraction failed: {e}")

# Ejecuta al importar (Python carga sitecustomize automáticamente si está en PYTHONPATH)
_set_limit()
