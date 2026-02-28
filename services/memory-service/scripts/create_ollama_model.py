"""
Crear modelo en Ollama desde archivo GGUF
Este script se ejecuta en el HOST (no en Docker)
"""

import subprocess
from pathlib import Path
import sys


def create_ollama_model(gguf_file: str, model_name: str = "casiopy:personality"):
    """
    Crear modelo en Ollama

    Args:
        gguf_file: Path al archivo GGUF
        model_name: Nombre del modelo en Ollama

    Returns:
        True si se creó exitosamente
    """
    print("=" * 60)
    print("🦙 CREANDO MODELO EN OLLAMA")
    print("=" * 60)
    print(f"📄 GGUF: {gguf_file}")
    print(f"📛 Modelo: {model_name}")
    print()

    # Verificar que existe el archivo
    gguf_path = Path(gguf_file)
    if not gguf_path.exists():
        print(f"❌ Error: Archivo GGUF no encontrado: {gguf_file}")
        return False

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
    modelfile_content = f"""FROM {gguf_path.absolute()}

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

    # Guardar Modelfile
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    modelfile_path = models_dir / f"Modelfile_{model_name.replace(':', '_')}"

    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    print(f"📝 Modelfile creado: {modelfile_path}")

    # Crear modelo en Ollama
    print(f"🔄 Creando modelo '{model_name}' en Ollama...")
    print("⏳ Esto puede tomar 1-2 minutos...")
    print()

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
        print(f"❌ Error al crear modelo: {e.stderr}")
        return False

    # Éxito
    print()
    print("=" * 60)
    print("✅ MODELO LISTO PARA USAR")
    print("=" * 60)
    print(f"📦 Modelo: {model_name}")
    print()
    print("🧪 PRUÉBALO:")
    print(f"   ollama run {model_name}")
    print()
    print("💬 PREGUNTAS DE PRUEBA:")
    print('   "¿Quién eres?"')
    print('   "¿Qué opinas de PHP?"')
    print('   "Hola, ¿cómo estás?"')
    print()

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Crear modelo en Ollama desde GGUF")
    parser.add_argument(
        "--gguf-file",
        type=str,
        required=True,
        help="Path al archivo GGUF",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="casiopy:personality",
        help="Nombre del modelo en Ollama",
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
            print("   Inicia Ollama primero")
            exit(1)
    except FileNotFoundError:
        print("❌ Error: Ollama no está instalado")
        print("   Instala desde: https://ollama.ai")
        exit(1)

    success = create_ollama_model(args.gguf_file, args.model_name)

    exit(0 if success else 1)


if __name__ == "__main__":
    main()
