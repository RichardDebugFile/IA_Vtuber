"""
Entrenamiento de LoRA de Personalidad (Capa 1) con Unsloth
Hardware: RTX 5060 Ti (16GB VRAM)

Este script puede ejecutarse desde línea de comandos o desde el dashboard web.

Uso:
    python train_personality_lora.py --dataset path/to/dataset.jsonl --epochs 3 --batch_size 4 --learning_rate 2e-4
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from datasets import Dataset
import torch

# Importar Unsloth
try:
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments
except ImportError:
    print("[ERROR] Unsloth no esta instalado")
    print("[INFO] Instalar con: pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"")
    sys.exit(1)


# ============================================================
# CONFIGURACION PARA RTX 5060 Ti (16GB VRAM)
# ============================================================

# Modelo base
BASE_MODEL = "NousResearch/Hermes-3-Llama-3.1-8B"

# Configuracion de cuantizacion y precision
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True  # 4-bit quantization para ahorrar VRAM
DTYPE = None  # Auto-detect (bfloat16 en Blackwell)

# Configuracion de LoRA
LORA_RANK = 16  # Rank alto para personalidad (mas parametros)
LORA_ALPHA = 32  # Alpha = 2 * rank (recomendado)
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

# Configuracion de entrenamiento (valores por defecto)
DEFAULT_BATCH_SIZE = 2  # Batch pequeño por VRAM
DEFAULT_GRADIENT_ACCUMULATION = 4  # Simula batch de 8
DEFAULT_LEARNING_RATE = 2e-4
DEFAULT_NUM_EPOCHS = 3
WARMUP_STEPS = 100
LOGGING_STEPS = 1  # Log cada step para el dashboard
SAVE_STEPS = 100

# Directorios
SCRIPT_DIR = Path(__file__).parent
SERVICE_DIR = SCRIPT_DIR.parent
OUTPUT_BASE_DIR = SERVICE_DIR / "models" / "lora_adapters"
DATASET_DIR = SERVICE_DIR / "exports" / "personality"


def print_log(message, level="INFO"):
    """Imprime mensajes en formato parseable por el dashboard"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def load_dataset_from_jsonl(file_path: str) -> Dataset:
    """
    Cargar dataset desde archivo JSONL

    Formato esperado:
    {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ],
        "metadata": {...}
    }
    """
    print_log(f"Cargando dataset: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f]

    print_log(f"Ejemplos cargados: {len(data)}")

    # Convertir a formato de entrenamiento
    formatted_data = []
    for entry in data:
        messages = entry["messages"]

        # Convertir a formato ChatML
        conversation = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                conversation += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == "user":
                conversation += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == "assistant":
                conversation += f"<|im_start|>assistant\n{content}<|im_end|>\n"

        formatted_data.append({"text": conversation})

    return Dataset.from_list(formatted_data)


def train_personality_lora(
    dataset_file: str,
    epochs: int = DEFAULT_NUM_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    gradient_accumulation: int = DEFAULT_GRADIENT_ACCUMULATION
):
    """
    Entrenar LoRA de personalidad

    Args:
        dataset_file: Path al archivo .jsonl con los datos
        epochs: Numero de epocas de entrenamiento
        batch_size: Tamano del batch
        learning_rate: Tasa de aprendizaje
        gradient_accumulation: Steps de acumulacion de gradientes
    """
    print_log("=" * 60)
    print_log("ENTRENAMIENTO DE LoRA DE PERSONALIDAD (Capa 1)")
    print_log("=" * 60)

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print_log(f"GPU: {gpu_name}")
        print_log(f"VRAM disponible: {vram_gb:.2f} GB")
    else:
        print_log("GPU: CPU (ADVERTENCIA: Sera muy lento)", "WARNING")

    print_log("")

    # Cargar dataset
    dataset = load_dataset_from_jsonl(dataset_file)
    print_log(f"Total de ejemplos: {len(dataset)}")
    print_log("")

    # Cargar modelo base con Unsloth
    print_log("Cargando modelo base con Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )
    print_log("Modelo base cargado")
    print_log("")

    # Añadir adaptadores LoRA
    print_log("Configurando adaptadores LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_RANK,
        target_modules=TARGET_MODULES,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",  # Optimización de Unsloth
        random_state=3407,
    )
    print_log(f"LoRA configurado: Rank={LORA_RANK}, Alpha={LORA_ALPHA}")
    print_log("")

    # Crear directorio de salida con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE_DIR / f"personality_v1_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Configurar trainer
    print_log("Configurando entrenamiento...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,  # No juntar ejemplos (mejor para personalidad)
        args=TrainingArguments(
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=epochs,
            learning_rate=learning_rate,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=LOGGING_STEPS,
            optim="adamw_8bit",  # Optimizer optimizado
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=str(output_dir),
            save_steps=SAVE_STEPS,
            save_total_limit=3,
            report_to="none",  # Desactivar wandb, tensorboard, etc.
        ),
    )

    print_log("Trainer configurado")
    print_log("")

    # Entrenar
    print_log("Iniciando entrenamiento...")
    print_log(f"   Batch size efectivo: {batch_size * gradient_accumulation}")
    print_log(f"   Epocas: {epochs}")
    print_log(f"   Learning rate: {learning_rate}")
    print_log("")

    trainer_stats = trainer.train()

    print_log("")
    print_log("=" * 60)
    print_log("ENTRENAMIENTO COMPLETADO")
    print_log("=" * 60)
    print_log(f"Tiempo total: {trainer_stats.metrics['train_runtime']:.2f}s")
    print_log(f"Loss final: {trainer_stats.metrics['train_loss']:.4f}")
    print_log("")

    # Guardar modelo
    print_log(f"Guardando LoRA en: {output_dir}")
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Guardar metadata
    metadata = {
        "model_type": "personality_core",
        "base_model": BASE_MODEL,
        "lora_rank": LORA_RANK,
        "lora_alpha": LORA_ALPHA,
        "training_samples": len(dataset),
        "num_epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "gradient_accumulation": gradient_accumulation,
        "trained_at": datetime.now().isoformat(),
        "final_loss": float(trainer_stats.metrics['train_loss']),
        "total_time": trainer_stats.metrics['train_runtime'],
    }

    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print_log("Modelo y metadata guardados")
    print_log("")
    print_log("PROXIMOS PASOS:")
    print_log("   1. Validar el LoRA con test_personality.py")
    print_log("   2. Si pasa las pruebas, NO modificar nunca mas")
    print_log("   3. Usar este LoRA como base para entrenamientos episodicos")
    print_log("")

    return output_dir


def main():
    """CLI para entrenar LoRA de personalidad"""
    import argparse

    parser = argparse.ArgumentParser(description="Entrenar LoRA de Personalidad (Capa 1)")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path al archivo .jsonl con datos de entrenamiento",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_NUM_EPOCHS,
        help=f"Numero de epocas (default: {DEFAULT_NUM_EPOCHS})",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Tamano del batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=DEFAULT_LEARNING_RATE,
        help=f"Tasa de aprendizaje (default: {DEFAULT_LEARNING_RATE})",
    )
    parser.add_argument(
        "--gradient_accumulation",
        type=int,
        default=DEFAULT_GRADIENT_ACCUMULATION,
        help=f"Steps de acumulacion de gradientes (default: {DEFAULT_GRADIENT_ACCUMULATION})",
    )

    args = parser.parse_args()

    # Verificar que el dataset existe
    if not os.path.exists(args.dataset):
        print_log(f"Error: Dataset no encontrado: {args.dataset}", "ERROR")
        print_log("Genera el dataset primero con: python create_initial_personality_dataset_natural.py", "INFO")
        sys.exit(1)

    # Verificar GPU
    if not torch.cuda.is_available():
        print_log("ADVERTENCIA: No se detecto GPU CUDA", "WARNING")
        response = input("Continuar con CPU? (muy lento) [y/N]: ")
        if response.lower() != 'y':
            sys.exit(0)

    # Entrenar
    output_path = train_personality_lora(
        dataset_file=args.dataset,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        gradient_accumulation=args.gradient_accumulation
    )

    print_log(f"LoRA de personalidad guardado en: {output_path}")


if __name__ == "__main__":
    main()
