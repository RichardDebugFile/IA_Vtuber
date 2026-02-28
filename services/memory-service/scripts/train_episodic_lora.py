"""
Entrenamiento de LoRA Episódico (Capa 2) con Unsloth
Hardware: RTX 5060 Ti (16GB VRAM)

Este script se ejecuta SEMANALMENTE para añadir nuevas conversaciones
sobre el LoRA de personalidad CONGELADO.
"""

import os
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
    from peft import PeftModel
except ImportError:
    print("❌ Error: Unsloth no está instalado")
    print("   Instalar con: pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"")
    exit(1)


# ============================================================
# CONFIGURACIÓN PARA RTX 5060 Ti (16GB VRAM)
# ============================================================

# Modelo base
BASE_MODEL = "NousResearch/Hermes-3-Llama-3.1-8B"

# LoRA de personalidad (CONGELADO)
PERSONALITY_LORA_PATH = "./lora_adapters/personality_core_v1"

# Configuración de cuantización
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True
DTYPE = None  # Auto-detect

# Configuración de LoRA EPISÓDICO (más ligero que personalidad)
LORA_RANK = 8  # Rank más bajo que personalidad (16)
LORA_ALPHA = 16  # Alpha = 2 * rank
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "v_proj"]  # Solo attention (más específico)

# Configuración de entrenamiento (más rápido que personalidad)
BATCH_SIZE = 4  # Batch más grande (menos parámetros)
GRADIENT_ACCUMULATION = 2
LEARNING_RATE = 1e-4  # Learning rate más bajo (fine-tuning fino)
NUM_EPOCHS = 2  # Menos épocas
WARMUP_STEPS = 50
LOGGING_STEPS = 5
SAVE_STEPS = 50

# Directorios
OUTPUT_BASE_DIR = "./lora_adapters/episodic"


def load_dataset_from_jsonl(file_path: str) -> Dataset:
    """Cargar dataset desde archivo JSONL"""
    print(f"📂 Cargando dataset: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f]

    print(f"✅ Ejemplos cargados: {len(data)}")

    # Convertir a formato ChatML
    formatted_data = []
    for entry in data:
        messages = entry["messages"]

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


def train_episodic_lora(dataset_file: str, week_number: int):
    """
    Entrenar LoRA episódico semanal

    Este LoRA se entrena sobre el modelo base + personality LoRA (congelado)

    Args:
        dataset_file: Path al archivo .jsonl
        week_number: Número de semana
    """
    output_dir = f"{OUTPUT_BASE_DIR}/week_{week_number:03d}"

    print("=" * 60)
    print(f"📅 ENTRENAMIENTO DE LoRA EPISÓDICO - SEMANA {week_number}")
    print("=" * 60)
    print(f"📊 GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f"💾 VRAM disponible: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    print()

    # Verificar que existe el LoRA de personalidad
    if not os.path.exists(PERSONALITY_LORA_PATH):
        print(f"❌ Error: LoRA de personalidad no encontrado en: {PERSONALITY_LORA_PATH}")
        print("   Entrena primero el LoRA de personalidad con train_personality_lora.py")
        exit(1)

    print(f"✅ LoRA de personalidad encontrado: {PERSONALITY_LORA_PATH}")
    print()

    # Cargar dataset
    dataset = load_dataset_from_jsonl(dataset_file)
    print(f"📈 Total de ejemplos de esta semana: {len(dataset)}")
    print()

    # Cargar modelo base
    print("🔄 Cargando modelo base...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )
    print("✅ Modelo base cargado")

    # Cargar LoRA de personalidad (CONGELADO - no entrenable)
    print("🔒 Cargando LoRA de personalidad (CONGELADO)...")
    model = PeftModel.from_pretrained(
        model,
        PERSONALITY_LORA_PATH,
        is_trainable=False,  # ⚠️ CRÍTICO: NO modificar personalidad
    )
    print("✅ LoRA de personalidad cargado y congelado")
    print()

    # Añadir NUEVO adaptador episódico (entrenable)
    print("🔧 Añadiendo adaptador episódico...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_RANK,
        target_modules=TARGET_MODULES,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )
    print(f"✅ Adaptador episódico configurado: Rank={LORA_RANK}")
    print()

    # Verificar parámetros entrenables
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"📊 Parámetros totales: {total_params:,}")
    print(f"📊 Parámetros entrenables: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
    print()

    # Configurar trainer
    print("⚙️  Configurando entrenamiento...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=LOGGING_STEPS,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=output_dir,
            save_steps=SAVE_STEPS,
            save_total_limit=2,
        ),
    )

    print("✅ Trainer configurado")
    print()

    # Entrenar
    print("🚀 Iniciando entrenamiento episódico...")
    print(f"   Batch size efectivo: {BATCH_SIZE * GRADIENT_ACCUMULATION}")
    print(f"   Épocas: {NUM_EPOCHS}")
    print(f"   Learning rate: {LEARNING_RATE}")
    print()

    trainer_stats = trainer.train()

    print()
    print("=" * 60)
    print("✅ ENTRENAMIENTO EPISÓDICO COMPLETADO")
    print("=" * 60)
    print(f"⏱️  Tiempo total: {trainer_stats.metrics['train_runtime']:.2f}s")
    print(f"📉 Loss final: {trainer_stats.metrics['train_loss']:.4f}")
    print()

    # Guardar SOLO el adaptador episódico (no la personalidad)
    print(f"💾 Guardando LoRA episódico en: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Guardar metadata
    metadata = {
        "model_type": "episodic",
        "week_number": week_number,
        "base_model": BASE_MODEL,
        "personality_lora": PERSONALITY_LORA_PATH,
        "lora_rank": LORA_RANK,
        "lora_alpha": LORA_ALPHA,
        "training_samples": len(dataset),
        "num_epochs": NUM_EPOCHS,
        "learning_rate": LEARNING_RATE,
        "trained_at": datetime.now().isoformat(),
        "final_loss": float(trainer_stats.metrics['train_loss']),
        "total_time": trainer_stats.metrics['train_runtime'],
    }

    with open(f"{output_dir}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("✅ Modelo episódico y metadata guardados")
    print()
    print("📋 PRÓXIMOS PASOS:")
    print(f"   1. Validar con: python test_personality.py --episodic-week {week_number}")
    print(f"   2. Si pasa validación, fusionar con: python deploy_to_ollama.py --week {week_number}")
    print(f"   3. Si falla validación, revertir a semana anterior")
    print()

    return output_dir


def main():
    """CLI para entrenar LoRA episódico"""
    import argparse

    parser = argparse.ArgumentParser(description="Entrenar LoRA Episódico (Capa 2)")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path al archivo .jsonl con datos semanales",
    )
    parser.add_argument(
        "--week",
        type=int,
        required=True,
        help="Número de semana (1-52)",
    )

    args = parser.parse_args()

    # Verificar dataset
    if not os.path.exists(args.dataset):
        print(f"❌ Error: Dataset no encontrado: {args.dataset}")
        print(f"   Genera el dataset con: python export_training_data.py --type episodic --week {args.week}")
        exit(1)

    # Verificar GPU
    if not torch.cuda.is_available():
        print("⚠️  ADVERTENCIA: No se detectó GPU CUDA")
        response = input("¿Continuar con CPU? (muy lento) [y/N]: ")
        if response.lower() != 'y':
            exit(0)

    # Entrenar
    output_path = train_episodic_lora(args.dataset, args.week)

    print(f"✅ LoRA episódico semana {args.week} guardado en: {output_path}")


if __name__ == "__main__":
    main()
