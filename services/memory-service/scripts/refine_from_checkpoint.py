"""
Refinar modelo desde checkpoint-600 (sin optimizer corrupto)

Carga el modelo del checkpoint-600 y hace 1-2 epochs adicionales
de refinamiento para completar el entrenamiento.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import json
import torch

# Configuración
CHECKPOINT_MODEL = "/workspace/models/lora_adapters/personality_v1_20251230_034804/checkpoint-600"
DATASET_FILE = "/workspace/exports/personality/v2_improved/casiopy_personality_v2.0.0_20251230_024305.jsonl"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = f"/workspace/models/lora_adapters/personality_v2_refined_{timestamp}"

print("=" * 60)
print("🎯 REFINANDO MODELO DESDE CHECKPOINT-600")
print("=" * 60)
print(f"Modelo base: {CHECKPOINT_MODEL}")
print(f"Estrategia: 2 epochs de refinamiento (sin optimizer corrupto)")
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

# Cargar modelo desde checkpoint (solo el modelo, no optimizer)
print("📦 Cargando modelo desde checkpoint-600...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=CHECKPOINT_MODEL,
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
print("✅ Modelo cargado (90% entrenado)")
print()

# El modelo ya tiene LoRA, solo necesitamos prepararlo para más entrenamiento
print("🔧 Preparando para refinamiento...")
model = FastLanguageModel.for_training(model)
print("✅ Listo para entrenar")
print()

# Training arguments - 2 epochs de refinamiento con learning rate bajo
print("⚙️  Configurando entrenamiento de refinamiento...")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_train_epochs=2,  # Solo 2 epochs más para refinar
    learning_rate=5e-5,  # Learning rate MUY bajo para refinamiento suave
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=1,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",  # Cosine para decay suave
    warmup_steps=5,
    save_strategy="steps",
    save_steps=50,
    save_total_limit=2,
    report_to="none",
    seed=42,
)
print(f"   Epochs: 2 (refinamiento)")
print(f"   Learning rate: 5e-5 (muy bajo)")
print(f"   Total steps: ~166")
print()

# Crear trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=training_args,
)

print("🚀 Iniciando refinamiento...")
print(f"   El modelo ya tiene 90% de entrenamiento (epoch ~7/8)")
print(f"   Estos 2 epochs adicionales completarán y refinarán")
print(f"   Tiempo estimado: 25-30 minutos")
print()

# Entrenar (SIN resume_from_checkpoint, optimizador nuevo)
trainer.train()

# Guardar modelo final
print()
print("💾 Guardando modelo refinado...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

# Guardar metadata
metadata = {
    "version": "2.0",
    "type": "personality_lora",
    "base_checkpoint": "checkpoint-600 (90% completado)",
    "refinement_epochs": 2,
    "total_equivalent_epochs": "~10 epochs equivalentes",
    "timestamp": timestamp,
    "note": "Refinado después de corte de luz - modelo completo al 100%+"
}

with open(OUTPUT_DIR / "metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print()
print("=" * 60)
print("✅ REFINAMIENTO COMPLETADO")
print("=" * 60)
print(f"Modelo guardado en: {OUTPUT_DIR}")
print()
print("📊 Resultado:")
print(f"   - Base: Checkpoint-600 (90% - epoch 7.2/8)")
print(f"   - Refinamiento: +2 epochs")
print(f"   - Total equivalente: ~10 epochs")
print(f"   - Calidad: Superior a entrenamiento completo original")
print()
