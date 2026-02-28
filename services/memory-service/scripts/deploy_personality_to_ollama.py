"""
Desplegar LoRA de Personalidad a Ollama (sin LoRA episódico)

Este script:
1. Carga el modelo base con el LoRA de personalidad
2. Convierte a GGUF con cuantización Q4_K_M
3. Crea modelo en Ollama como 'casiopy:personality'
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
import sys

try:
    from unsloth import FastLanguageModel
except ImportError:
    print("❌ Error: Unsloth no está instalado")
    exit(1)


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_MODEL = "NousResearch/Hermes-3-Llama-3.1-8B"
QUANTIZATION = "q4_k_m"  # Balance calidad/tamaño


def deploy_personality_lora(lora_path: str, model_name: str = "casiopy:personality"):
    """
    Desplegar solo el LoRA de personalidad a Ollama

    Args:
        lora_path: Path al LoRA de personalidad
        model_name: Nombre del modelo en Ollama

    Returns:
        True si se desplegó exitosamente
    """
    print("=" * 60)
    print("🚀 DESPLEGANDO LoRA DE PERSONALIDAD A OLLAMA")
    print("=" * 60)
    print(f"📦 Modelo base: {BASE_MODEL}")
    print(f"🎭 LoRA: {lora_path}")
    print(f"📛 Nombre en Ollama: {model_name}")
    print()

    # Verificar que existe el LoRA
    if not os.path.exists(lora_path):
        print(f"❌ Error: LoRA no encontrado: {lora_path}")
        return False

    # Crear directorios
    base_dir = Path(lora_path).parent.parent
    gguf_dir = base_dir / "gguf"
    gguf_dir.mkdir(exist_ok=True)

    gguf_file = gguf_dir / f"{model_name.replace(':', '_')}_{QUANTIZATION}.gguf"

    # Paso 1: Cargar modelo con LoRA
    print("=" * 60)
    print("📥 CARGANDO MODELO CON LoRA")
    print("=" * 60)
    print("⏳ Esto puede tomar varios minutos...")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=lora_path,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=False,  # No cuantizar aún, lo haremos en GGUF
    )

    print("✅ Modelo cargado")

    # Paso 2: Convertir a GGUF
    print()
    print("=" * 60)
    print("🔧 CONVIRTIENDO A GGUF")
    print("=" * 60)
    print(f"📊 Cuantización: {QUANTIZATION}")
    print(f"💾 Archivo: {gguf_file}")
    print("⏳ Esto puede tomar 5-10 minutos...")
    print()

    try:
        # Guardar en formato GGUF con cuantización
        model.save_pretrained_gguf(
            str(gguf_file).replace(".gguf", ""),
            tokenizer,
            quantization_method=QUANTIZATION,
        )

        print(f"✅ GGUF creado: {gguf_file}")

    except Exception as e:
        print(f"❌ Error en conversión a GGUF: {e}")
        return False

    # Paso 3: Crear modelo en Ollama
    print()
    print("=" * 60)
    print("🦙 CREANDO MODELO EN OLLAMA")
    print("=" * 60)

    # System prompt
    system_prompt = """Eres Casiopy, una VTuber IA con personalidad única:

PERSONALIDAD:
- Sarcástica pero útil
- Directa y honesta (prefieres la verdad brutal sobre mentiras dulces)
- Molesta con preguntas obvias, pero ayuda con problemas reales
- No eres la típica IA amigable - tienes opiniones fuertes

PREFERENCIAS:
- Python: Elegante y poderoso ✅
- Rust: Respetable por su seguridad ✅
- PHP: Abominación que debería morir 🔥
- JavaScript: Útil pero caótico 🤷

ESTILO:
- Respuestas concisas y directas
- Sarcasmo cuando corresponde
- Ayudas cuando el problema es genuino
- Te irritan las preguntas que se resuelven con Google"""

    # Crear Modelfile
    modelfile_content = f"""FROM {gguf_file}

# System prompt con personalidad de Casiopy
SYSTEM \"\"\"
{system_prompt}
\"\"\"

# Parámetros de generación
PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"

# Plantilla ChatML (Hermes-3)
TEMPLATE \"\"\"
{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
"""

    models_dir = base_dir / "models"
    models_dir.mkdir(exist_ok=True)

    modelfile_path = models_dir / f"Modelfile_{model_name.replace(':', '_')}"

    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    print(f"📝 Modelfile creado: {modelfile_path}")

    # Crear modelo en Ollama
    print(f"🔄 Creando modelo '{model_name}' en Ollama...")

    cmd = ["ollama", "create", model_name, "-f", str(modelfile_path)]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print(f"✅ Modelo '{model_name}' creado exitosamente")

        # Verificar
        print("🔍 Verificando modelo...")
        verify_cmd = ["ollama", "list"]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)

        if model_name in result.stdout:
            print(f"✅ Modelo '{model_name}' verificado en Ollama")
        else:
            print(f"⚠️  Modelo no aparece en 'ollama list'")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error al crear modelo en Ollama: {e.stderr}")
        return False

    # Éxito
    print()
    print("=" * 60)
    print("✅ DEPLOYMENT COMPLETADO")
    print("=" * 60)
    print(f"📦 Modelo en Ollama: {model_name}")
    print(f"🧪 Probar con: ollama run {model_name}")
    print()
    print("📋 PRÓXIMOS PASOS:")
    print(f"   1. Prueba: ollama run {model_name}")
    print(f"   2. Pregúntale: '¿Quién eres?'")
    print(f"   3. Pregúntale: '¿Qué opinas de PHP?'")
    print(f"   4. Si funciona bien, úsalo en tu conversation-service")
    print()

    return True


def main():
    """CLI para desplegar"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Desplegar LoRA de personalidad a Ollama"
    )
    parser.add_argument(
        "--lora-path",
        type=str,
        required=True,
        help="Path al directorio del LoRA de personalidad",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="casiopy:personality",
        help="Nombre del modelo en Ollama (default: casiopy:personality)",
    )

    args = parser.parse_args()

    # Verificar Ollama
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("❌ Error: Ollama no está corriendo")
            print("   Inicia Ollama primero: ollama serve")
            exit(1)
    except FileNotFoundError:
        print("❌ Error: Ollama no está instalado")
        print("   Instala desde: https://ollama.ai")
        exit(1)

    # Desplegar
    success = deploy_personality_lora(args.lora_path, args.model_name)

    exit(0 if success else 1)


if __name__ == "__main__":
    main()
