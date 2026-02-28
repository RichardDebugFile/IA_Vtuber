"""
Exportar LoRA a formato GGUF
Solo hace la conversión, el deployment a Ollama se hace desde el host
"""

import os
from pathlib import Path
import sys

try:
    from unsloth import FastLanguageModel
except ImportError:
    print("❌ Error: Unsloth no está instalado")
    exit(1)


def export_to_gguf(lora_path: str, output_name: str = "casiopy_personality"):
    """
    Exportar LoRA a GGUF

    Args:
        lora_path: Path al LoRA
        output_name: Nombre base del archivo de salida

    Returns:
        Path al archivo GGUF
    """
    print("=" * 60)
    print("🔧 EXPORTANDO LoRA A GGUF")
    print("=" * 60)
    print(f"📥 LoRA: {lora_path}")
    print()

    # Verificar que existe
    if not os.path.exists(lora_path):
        print(f"❌ Error: LoRA no encontrado: {lora_path}")
        return None

    # Directorio de salida
    base_dir = Path(lora_path).parent.parent
    gguf_dir = base_dir / "gguf"
    gguf_dir.mkdir(exist_ok=True)

    output_path = gguf_dir / output_name

    print("⏳ Cargando modelo con LoRA (4bit para ahorrar VRAM)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=lora_path,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,  # Cargar en 4bit para ahorrar VRAM
    )
    print("✅ Modelo cargado")

    print()
    print("🔧 Convirtiendo a GGUF (Q4_K_M)...")
    print("⏳ Esto puede tomar 5-10 minutos...")
    print()

    try:
        model.save_pretrained_gguf(
            str(output_path),
            tokenizer,
            quantization_method="q4_k_m",
        )

        # Encontrar el archivo generado
        gguf_files = list(gguf_dir.glob(f"{output_name}*.gguf"))

        if not gguf_files:
            print("❌ Error: No se generó archivo GGUF")
            return None

        gguf_file = gguf_files[0]
        print(f"✅ GGUF exportado: {gguf_file}")
        print()
        print("=" * 60)
        print("✅ EXPORTACIÓN COMPLETADA")
        print("=" * 60)
        print(f"📄 Archivo: {gguf_file}")
        print(f"📏 Tamaño: {gguf_file.stat().st_size / (1024**3):.2f} GB")
        print()

        return str(gguf_file)

    except Exception as e:
        print(f"❌ Error en conversión: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Exportar LoRA a GGUF")
    parser.add_argument(
        "--lora-path",
        type=str,
        required=True,
        help="Path al directorio del LoRA",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default="casiopy_personality",
        help="Nombre base del archivo GGUF",
    )

    args = parser.parse_args()

    gguf_file = export_to_gguf(args.lora_path, args.output_name)

    if gguf_file:
        print("📋 PRÓXIMO PASO:")
        print(f"   Desde el HOST (no Docker), ejecuta:")
        print(f"   python scripts/create_ollama_model.py --gguf-file \"{gguf_file}\"")
        print()
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
