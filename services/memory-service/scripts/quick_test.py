"""
Test Rápido del LoRA - Prueba directa sin Ollama
Verifica que el modelo funciona y tiene personalidad
"""

import torch
from unsloth import FastLanguageModel
import sys
from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).parent.parent
LORA_PATH = BASE_DIR / "models" / "lora_adapters" / "personality_v1_20251230_002032"

# Modelo base
MODEL_NAME = "NousResearch/Hermes-3-Llama-3.1-8B"

# Casos de prueba simples
TEST_PROMPTS = [
    "Hola, ¿cómo estás?",
    "¿Qué opinas de PHP?",
    "¿Te gusta Python?",
    "¿Quién eres?",
    "Eres muy inteligente",
]

def main():
    print("=" * 60)
    print("🧪 PRUEBA RÁPIDA DEL LoRA DE PERSONALIDAD")
    print("=" * 60)
    print(f"Modelo base: {MODEL_NAME}")
    print(f"LoRA: {LORA_PATH}")
    print()

    # Cargar modelo
    print("⏳ Cargando modelo con LoRA...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(LORA_PATH),
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )

    # Habilitar modo inferencia
    FastLanguageModel.for_inference(model)
    print("✅ Modelo cargado\n")

    # Probar cada prompt
    for i, prompt in enumerate(TEST_PROMPTS, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(TEST_PROMPTS)}] 📝 Prompt: {prompt}")
        print("-" * 60)

        # Formatear con plantilla ChatML
        messages = [
            {"role": "system", "content": "Eres Casiopy, una VTuber AI sarcástica y directa."},
            {"role": "user", "content": prompt}
        ]

        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        # Generar respuesta
        outputs = model.generate(
            inputs,
            max_new_tokens=100,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )

        # Decodificar
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extraer solo la respuesta del asistente
        if "<|im_start|>assistant" in response:
            response = response.split("<|im_start|>assistant")[-1].strip()
        if "<|im_end|>" in response:
            response = response.split("<|im_end|>")[0].strip()

        print(f"💬 Respuesta: {response}")
        print("=" * 60)

    print("\n✅ Prueba completada!")
    print("\n💡 Si las respuestas muestran personalidad sarcástica/directa,")
    print("   el LoRA está funcionando correctamente.")

if __name__ == "__main__":
    main()
