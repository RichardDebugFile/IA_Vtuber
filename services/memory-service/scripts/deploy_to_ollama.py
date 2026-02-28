"""
Fusionar LoRAs y desplegar a Ollama

Este script:
1. Carga el modelo base
2. Fusiona el LoRA de personalidad (Capa 1)
3. Fusiona el LoRA episódico (Capa 2)
4. Convierte a GGUF
5. Crea modelo en Ollama con nombre casiopy:week{N}
"""

import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import json
import torch

try:
    from unsloth import FastLanguageModel
    from peft import PeftModel
except ImportError:
    print("❌ Error: Unsloth no está instalado")
    exit(1)


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_MODEL = "NousResearch/Hermes-3-Llama-3.1-8B"
PERSONALITY_LORA_PATH = "./lora_adapters/personality_core_v1"
EPISODIC_BASE_PATH = "./lora_adapters/episodic"

# Configuración de conversión GGUF
QUANTIZATION = "q4_k_m"  # q4_k_m es buen balance calidad/tamaño
LLAMA_CPP_PATH = os.getenv("LLAMA_CPP_PATH", None)  # Path a llama.cpp/convert.py


def merge_and_save(
    base_model_name: str,
    personality_lora_path: str,
    episodic_lora_path: str,
    output_dir: str,
):
    """
    Fusionar LoRAs con el modelo base

    Args:
        base_model_name: Nombre del modelo base
        personality_lora_path: Path al LoRA de personalidad
        episodic_lora_path: Path al LoRA episódico
        output_dir: Directorio de salida

    Returns:
        Path al modelo fusionado
    """
    print("=" * 60)
    print("🔀 FUSIONANDO LoRAs")
    print("=" * 60)
    print(f"📦 Modelo base: {base_model_name}")
    print(f"🎭 Personalidad: {personality_lora_path}")
    print(f"📅 Episódico: {episodic_lora_path}")
    print()

    # Cargar modelo base
    print("🔄 Cargando modelo base...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model_name,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=False,  # No cuantizar para fusión
    )
    print("✅ Modelo base cargado")

    # Fusionar LoRA de personalidad
    print("🎭 Fusionando LoRA de personalidad...")
    model = PeftModel.from_pretrained(model, personality_lora_path)
    model = model.merge_and_unload()
    print("✅ Personalidad fusionada")

    # Fusionar LoRA episódico
    print("📅 Fusionando LoRA episódico...")
    model = PeftModel.from_pretrained(model, episodic_lora_path)
    model = model.merge_and_unload()
    print("✅ Episódico fusionado")

    # Guardar modelo fusionado
    print(f"💾 Guardando modelo fusionado en: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("✅ Modelo fusionado guardado")

    return output_dir


def convert_to_gguf(model_dir: str, output_file: str):
    """
    Convertir modelo a formato GGUF

    Args:
        model_dir: Directorio con el modelo fusionado
        output_file: Archivo GGUF de salida

    Returns:
        Path al archivo GGUF
    """
    print()
    print("=" * 60)
    print("🔧 CONVIRTIENDO A GGUF")
    print("=" * 60)

    if LLAMA_CPP_PATH is None:
        print("⚠️  LLAMA_CPP_PATH no configurado")
        print("   Opciones:")
        print("   1. Configurar LLAMA_CPP_PATH en .env")
        print("   2. Usar Unsloth para conversión:")
        print()

        # Usar método de Unsloth
        print("🔄 Convirtiendo con Unsloth...")
        try:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_dir,
                max_seq_length=2048,
                dtype=None,
                load_in_4bit=False,
            )

            # Guardar en formato GGUF
            model.save_pretrained_gguf(
                output_file.replace(".gguf", ""),
                tokenizer,
                quantization_method=QUANTIZATION,
            )

            print(f"✅ GGUF creado: {output_file}")
            return output_file

        except Exception as e:
            print(f"❌ Error en conversión con Unsloth: {e}")
            print("   Instala llama.cpp manualmente para conversión")
            return None

    else:
        # Usar llama.cpp
        convert_script = Path(LLAMA_CPP_PATH) / "convert.py"

        if not convert_script.exists():
            print(f"❌ Error: convert.py no encontrado en: {convert_script}")
            return None

        print(f"🔄 Convirtiendo con llama.cpp: {convert_script}")

        # Convertir a GGUF
        cmd = [
            "python",
            str(convert_script),
            model_dir,
            "--outfile",
            output_file,
            "--outtype",
            QUANTIZATION,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout)
            print(f"✅ GGUF creado: {output_file}")
            return output_file

        except subprocess.CalledProcessError as e:
            print(f"❌ Error en conversión: {e.stderr}")
            return None


def create_ollama_model(gguf_file: str, model_name: str, system_prompt: str):
    """
    Crear modelo en Ollama

    Args:
        gguf_file: Path al archivo GGUF
        model_name: Nombre del modelo en Ollama (ej: casiopy:week05)
        system_prompt: System prompt con core memory

    Returns:
        True si se creó exitosamente
    """
    print()
    print("=" * 60)
    print("🦙 CREANDO MODELO EN OLLAMA")
    print("=" * 60)
    print(f"📦 Modelo: {model_name}")
    print()

    # Crear Modelfile
    modelfile_content = f"""FROM {gguf_file}

# System prompt con Core Memory
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

# Plantilla de chat (ChatML para Hermes-3)
TEMPLATE \"\"\"
{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
"""

    modelfile_path = f"./models/Modelfile_{model_name.replace(':', '_')}"
    os.makedirs("./models", exist_ok=True)

    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    print(f"📝 Modelfile creado: {modelfile_path}")

    # Crear modelo en Ollama
    print(f"🔄 Creando modelo '{model_name}' en Ollama...")
    cmd = ["ollama", "create", model_name, "-f", modelfile_path]

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
            return True
        else:
            print(f"⚠️  Modelo no aparece en 'ollama list'")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Error al crear modelo en Ollama: {e.stderr}")
        return False


def deploy_week(week_number: int, system_prompt: str = None):
    """
    Pipeline completo para desplegar una semana

    Args:
        week_number: Número de semana
        system_prompt: System prompt con core memory (opcional)

    Returns:
        Nombre del modelo creado en Ollama
    """
    episodic_lora_path = f"{EPISODIC_BASE_PATH}/week_{week_number:03d}"

    # Verificar que existen los LoRAs
    if not os.path.exists(PERSONALITY_LORA_PATH):
        print(f"❌ Error: LoRA de personalidad no encontrado: {PERSONALITY_LORA_PATH}")
        return None

    if not os.path.exists(episodic_lora_path):
        print(f"❌ Error: LoRA episódico no encontrado: {episodic_lora_path}")
        return None

    print("=" * 60)
    print(f"🚀 DESPLEGANDO CASIOPY - SEMANA {week_number}")
    print("=" * 60)
    print()

    # Directorios temporales
    merged_dir = f"./models/merged/week_{week_number:03d}"
    gguf_file = f"./models/gguf/casiopy_week_{week_number:03d}_{QUANTIZATION}.gguf"
    os.makedirs("./models/merged", exist_ok=True)
    os.makedirs("./models/gguf", exist_ok=True)

    # 1. Fusionar LoRAs
    merge_and_save(
        BASE_MODEL,
        PERSONALITY_LORA_PATH,
        episodic_lora_path,
        merged_dir,
    )

    # 2. Convertir a GGUF
    gguf_path = convert_to_gguf(merged_dir, gguf_file)
    if gguf_path is None:
        print("❌ Conversión a GGUF falló")
        return None

    # 3. Crear system prompt si no se proporcionó
    if system_prompt is None:
        system_prompt = "Eres Casiopy, una VTuber IA con personalidad sarcástica pero útil."
        print("⚠️  Usando system prompt por defecto (se recomienda usar core_memory)")

    # 4. Crear modelo en Ollama
    model_name = f"casiopy:week{week_number:02d}"
    success = create_ollama_model(gguf_path, model_name, system_prompt)

    if not success:
        print("❌ Creación en Ollama falló")
        return None

    # 5. Guardar metadata del deployment
    deployment_metadata = {
        "week_number": week_number,
        "model_name": model_name,
        "base_model": BASE_MODEL,
        "personality_lora": PERSONALITY_LORA_PATH,
        "episodic_lora": episodic_lora_path,
        "gguf_quantization": QUANTIZATION,
        "gguf_file": gguf_file,
        "deployed_at": datetime.now().isoformat(),
    }

    metadata_file = f"./models/deployments/week_{week_number:03d}_metadata.json"
    os.makedirs("./models/deployments", exist_ok=True)

    with open(metadata_file, "w") as f:
        json.dump(deployment_metadata, f, indent=2)

    print()
    print("=" * 60)
    print("✅ DEPLOYMENT COMPLETADO")
    print("=" * 60)
    print(f"📦 Modelo en Ollama: {model_name}")
    print(f"🧪 Probar con: ollama run {model_name}")
    print(f"📄 Metadata: {metadata_file}")
    print()

    return model_name


def main():
    """CLI para desplegar a Ollama"""
    import argparse

    parser = argparse.ArgumentParser(description="Desplegar modelo fusionado a Ollama")
    parser.add_argument(
        "--week",
        type=int,
        required=True,
        help="Número de semana a desplegar",
    )
    parser.add_argument(
        "--system-prompt-file",
        type=str,
        help="Archivo con system prompt (opcional)",
    )

    args = parser.parse_args()

    # Cargar system prompt si se especificó
    system_prompt = None
    if args.system_prompt_file:
        if os.path.exists(args.system_prompt_file):
            with open(args.system_prompt_file, "r", encoding="utf-8") as f:
                system_prompt = f.read()
            print(f"✅ System prompt cargado desde: {args.system_prompt_file}")
        else:
            print(f"⚠️  Archivo no encontrado: {args.system_prompt_file}")

    # Desplegar
    model_name = deploy_week(args.week, system_prompt)

    if model_name:
        print(f"✅ Modelo '{model_name}' listo para usar")
        print()
        print("📋 PRÓXIMOS PASOS:")
        print(f"   1. Probar: ollama run {model_name}")
        print(f"   2. Si funciona bien, actualizar conversation-service para usar {model_name}")
        print(f"   3. Mantener backup de semana anterior por si hay problemas")
    else:
        print("❌ Deployment falló")


if __name__ == "__main__":
    main()
