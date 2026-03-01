"""
Deploy Personality LoRA → Ollama

Pipeline:
  1. Carga modelo base Hermes-3 en 4-bit (VRAM ~4.5 GB)
  2. Aplica LoRA de personalidad y hace merge_and_unload()
  3. Guarda en fp16 safetensors (~16 GB RAM)
  4. Convierte a GGUF q4_k_m con llama.cpp (~4.7 GB)
  5. Registra como casiopy:v1 en Ollama

Uso:
  cd services/memory-service
  deploy-venv/Scripts/python scripts/deploy_lora_to_ollama.py
"""

import os
import sys
import subprocess
import shutil
import json
import urllib.request
import zipfile
from pathlib import Path

# Silenciar warning de symlinks en Windows (no afecta funcionalidad)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# ── Rutas ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent  # services/memory-service/

BASE_MODEL      = "unsloth/hermes-3-llama-3.1-8b-bnb-4bit"
LORA_PATH       = ROOT / "models/lora_adapters/personality_v2_refined_20251230_163256"
MERGED_DIR      = ROOT / "models/merged/casiopy_v1"
GGUF_FILE       = ROOT / "models/gguf/casiopy_v1_q4_k_m.gguf"
MODELFILE_PATH  = ROOT / "models/Modelfile_casiopy_v1"
OLLAMA_NAME     = "casiopy:v1"

# Unsloth busca "llama.cpp/" relativo al CWD.  CWD = ROOT al ejecutar.
LLAMA_CPP_DIR = ROOT / "llama.cpp"


# ── Preparar llama.cpp binaries para Unsloth ──────────────────────────────────
def setup_llama_cpp():
    """Descarga llama-quantize.exe de la última release de llama.cpp (CPU build)."""
    quantize_exe = LLAMA_CPP_DIR / "llama-quantize.exe"
    convert_py   = LLAMA_CPP_DIR / "convert_hf_to_gguf.py"

    # Copiar el convert_hf_to_gguf.py que ya tenemos
    LLAMA_CPP_DIR.mkdir(exist_ok=True)
    src = SCRIPT_DIR / "convert_hf_to_gguf.py"
    if src.exists() and not convert_py.exists():
        shutil.copy2(str(src), str(convert_py))

    if quantize_exe.exists():
        print(f"  llama-quantize.exe ya disponible")
        return

    print("  Descargando llama-quantize.exe desde llama.cpp releases (CPU build)...")
    api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
    req = urllib.request.Request(api_url, headers={"User-Agent": "deploy-lora-script/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        release = json.loads(resp.read())

    # Prioridad: avx2 > avx > noavx (solo CPU, sin CUDA — basta para quantizar)
    asset = None
    for priority in ["avx2", "avx", "noavx", "x64"]:
        for a in release["assets"]:
            name = a["name"].lower()
            if "win" in name and priority in name and name.endswith(".zip") and "cuda" not in name:
                asset = a
                break
        if asset:
            break

    if not asset:
        raise RuntimeError("No se encontró zip Windows CPU en release de llama.cpp")

    size_mb = asset["size"] // 1024 // 1024
    print(f"  Descargando {asset['name']} ({size_mb} MB)...")
    zip_path = LLAMA_CPP_DIR / asset["name"]
    req2 = urllib.request.Request(asset["browser_download_url"],
                                  headers={"User-Agent": "deploy-lora-script/1.0"})
    with urllib.request.urlopen(req2, timeout=300) as resp:
        with open(zip_path, "wb") as f:
            f.write(resp.read())

    # Extraer TODOS los archivos (DLLs + exes)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            # Aplanar estructura: extraer solo el nombre base al LLAMA_CPP_DIR
            basename = Path(member).name
            if not basename:
                continue
            data = zf.read(member)
            out = LLAMA_CPP_DIR / basename
            with open(out, "wb") as f:
                f.write(data)
    zip_path.unlink()

    # Unsloth busca "llama-quantize" sin extensión → crear copia
    if quantize_exe.exists() and not (LLAMA_CPP_DIR / "llama-quantize").exists():
        shutil.copy2(str(quantize_exe), str(LLAMA_CPP_DIR / "llama-quantize"))

    print(f"  llama-quantize.exe listo en {LLAMA_CPP_DIR}")


# ── Validaciones ───────────────────────────────────────────────────────────────
def check_prereqs():
    if not LORA_PATH.exists():
        print(f"ERROR: LoRA no encontrado en {LORA_PATH}")
        sys.exit(1)

    adapter_cfg = LORA_PATH / "adapter_config.json"
    if not adapter_cfg.exists():
        print(f"ERROR: adapter_config.json no encontrado")
        sys.exit(1)

    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Ollama no está disponible. Asegúrate de que esté corriendo.")
        sys.exit(1)

    print("[OK] Prerequisitos verificados")
    print(f"  LoRA: {LORA_PATH}")
    print(f"  Base model: {BASE_MODEL}")


# ── Paso 1-3: Merge LoRA + exportar GGUF con Unsloth ─────────────────────────
def merge_and_export_gguf():
    """
    Usa Unsloth para cargar el modelo base en 4-bit, aplicar el LoRA,
    mergear, y exportar directamente a GGUF q4_k_m.
    Unsloth maneja la dequantizacion correctamente.
    """
    import torch
    from unsloth import FastLanguageModel

    print("\n[1/2] Cargando modelo + LoRA con Unsloth (4-bit)...")
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    # Cargar el adapter directamente: Unsloth detecta adapter_config.json
    # y carga BASE_MODEL + LoRA como PeftModel (necesario para save_pretrained_gguf)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(LORA_PATH),
        max_seq_length=2048,
        dtype=None,       # auto: bf16 en Blackwell
        load_in_4bit=True,
    )
    print(f"  Modelo + LoRA cargado desde {LORA_PATH.name}")

    print("\n[2/2] Exportando a GGUF q4_k_m con Unsloth...")

    # Normalizar chat_template: transformers >= 4.47 lo guarda como dict {name: template}
    if isinstance(tokenizer.chat_template, dict):
        ct = tokenizer.chat_template
        tokenizer.chat_template = ct.get("default", next(iter(ct.values())))
        print("  chat_template normalizado de dict a str")

    # Proveer llama.cpp binaries (Unsloth los busca en CWD/llama.cpp/)
    setup_llama_cpp()
    # Asegurar que CWD = ROOT para que Unsloth encuentre "llama.cpp/" relativo
    os.chdir(str(ROOT))

    GGUF_FILE.parent.mkdir(parents=True, exist_ok=True)
    gguf_stem = str(GGUF_FILE.parent / GGUF_FILE.stem)

    model.save_pretrained_gguf(
        gguf_stem,
        tokenizer,
        quantization_method="q4_k_m",
    )

    # Unsloth añade sufijo al nombre, buscar el archivo generado
    candidates = list(GGUF_FILE.parent.glob("*.gguf"))
    if not candidates:
        print("ERROR: No se encontró archivo GGUF generado")
        sys.exit(1)

    generated = max(candidates, key=lambda p: p.stat().st_mtime)
    if generated != GGUF_FILE:
        generated.rename(GGUF_FILE)

    print(f"  GGUF generado: {GGUF_FILE}")

    del model
    torch.cuda.empty_cache()

    return str(GGUF_FILE)


# ── Paso 4: Registrar en Ollama ───────────────────────────────────────────────
def create_ollama_model(gguf_path: str):
    print(f"\n[4/4] Creando modelo '{OLLAMA_NAME}' en Ollama...")

    # Obtener system prompt de memory-service (o usar el local)
    system_prompt = _get_system_prompt()

    modelfile_content = f"""FROM {gguf_path}

SYSTEM \"\"\"{system_prompt}\"\"\"

PARAMETER temperature 0.85
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
"""

    MODELFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODELFILE_PATH.write_text(modelfile_content, encoding="utf-8")
    print(f"  Modelfile: {MODELFILE_PATH}")

    result = subprocess.run(
        ["ollama", "create", OLLAMA_NAME, "-f", str(MODELFILE_PATH)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR al crear modelo en Ollama:\n{result.stderr}")
        sys.exit(1)

    print(f"  Modelo '{OLLAMA_NAME}' creado exitosamente")

    # Verificar
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if OLLAMA_NAME.split(":")[0] in result.stdout:
        print(f"  Verificado en 'ollama list'")
    else:
        print(f"  ADVERTENCIA: No aparece en 'ollama list' inmediatamente")


def _get_system_prompt() -> str:
    """Intentar obtener el system prompt del memory-service, o usar uno por defecto."""
    try:
        import urllib.request, json
        with urllib.request.urlopen(
            "http://127.0.0.1:8820/core-memory/system-prompt/generate", timeout=3
        ) as resp:
            data = json.loads(resp.read())
            prompt = data.get("system_prompt", "")
            if prompt:
                print("  System prompt obtenido de memory-service")
                return prompt
    except Exception:
        pass

    print("  Usando system prompt por defecto (memory-service no disponible)")
    return (
        "Eres Casiopy, una VTuber IA con una historia unica y personalidad compleja. "
        "Eres sarcastica pero genuinamente util. Respondes en espanol con naturalidad, "
        "tus respuestas son breves (20 palabras promedio) y directas."
    )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  DEPLOY: Personality LoRA -> Ollama (casiopy:v1)")
    print("=" * 60)

    check_prereqs()

    # Pasos 1-3: merge LoRA + exportar GGUF (Unsloth maneja todo)
    if GGUF_FILE.exists():
        print(f"\n[SKIP] GGUF ya existe: {GGUF_FILE}")
        gguf_path = str(GGUF_FILE)
    else:
        gguf_path = merge_and_export_gguf()

    # Paso 4: Ollama
    create_ollama_model(gguf_path)

    print("\n" + "=" * 60)
    print("  DEPLOY COMPLETADO")
    print("=" * 60)
    print(f"  Modelo: {OLLAMA_NAME}")
    print(f"  Probar: ollama run {OLLAMA_NAME}")
    print(f"\n  Actualiza .env del conversation-service:")
    print(f"  OLLAMA_MODEL={OLLAMA_NAME}")


if __name__ == "__main__":
    main()
