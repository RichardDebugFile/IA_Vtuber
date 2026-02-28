"""
Reanudar entrenamiento desde checkpoint

Este script reanuda el entrenamiento v3 desde el checkpoint-600
para completar los últimos 64 steps.
"""

import os
import sys
from pathlib import Path

# Añadir el directorio base al path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import json
import torch

# Configuración
CHECKPOINT_PATH = "/workspace/models/lora_adapters/personality_v1_20251230_034804/checkpoint-600"
DATASET_FILE = "/workspace/exports/personality/v2_improved/casiopy_personality_v2.0.0_20251230_024305.jsonl"
OUTPUT_DIR = "/workspace/models/lora_adapters/personality_v1_20251230_034804"

print("=" * 60)
print(" REANUDANDO ENTRENAMIENTO V3 DESDE CHECKPOINT-600")
print("=" * 60)
print(f"Checkpoint: {CHECKPOINT_PATH}")
print(f"Output: {OUTPUT_DIR}")
print()

# Cargar dataset
print("📥 Cargando dataset...")
with open(DATASET_FILE, "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f]

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

dataset = Dataset.from_list(formatted_data)
print(f"✅ {len(dataset)} ejemplos cargados")
print()

# Cargar modelo y tokenizer desde checkpoint
print("📦 Cargando modelo desde checkpoint...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=CHECKPOINT_PATH,
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
print("✅ Modelo cargado")
print()

# Preparar para entrenamiento
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

# Training arguments - continuar desde donde se quedó
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_train_epochs=8,  # Total epochs
    learning_rate=1.5e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=1,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="linear",
    warmup_steps=10,
    save_strategy="steps",
    save_steps=100,
    save_total_limit=3,
    report_to="none",
    seed=42,
    resume_from_checkpoint=CHECKPOINT_PATH,  # Clave para reanudar
)

# Crear trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=training_args,
)

print("🚀 Reanudando entrenamiento...")
print(f"   Desde: step 600/664 (90%)")
print(f"   Faltan: ~64 steps (10%)")
print(f"   Tiempo estimado: 10-15 minutos")
print()

# Entrenar
trainer.train(resume_from_checkpoint=CHECKPOINT_PATH)

# Guardar modelo final
print()
print("💾 Guardando modelo final...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print()
print("=" * 60)
print("✅ ENTRENAMIENTO V3 COMPLETADO AL 100%")
print("=" * 60)
print(f"Modelo guardado en: {OUTPUT_DIR}")
print()
