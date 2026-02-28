#!/bin/bash
# ============================================================
# SETUP DE ENTRENAMIENTO - CASIOPY MEMORY SERVICE
# ============================================================

set -e

echo "🎓 Configurando entorno de entrenamiento para Casiopy..."
echo ""

# Verificar Python
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python no está instalado"
    exit 1
fi

PYTHON_VERSION=$(python --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python $PYTHON_VERSION detectado"

# Verificar CUDA
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')
    echo "✅ GPU detectada: $GPU_NAME"
    echo "✅ CUDA Version: $CUDA_VERSION"
else
    echo "⚠️  ADVERTENCIA: nvidia-smi no encontrado"
    echo "   Entrenamiento será MUY lento sin GPU"
    read -p "¿Continuar de todos modos? [y/N]: " response
    if [ "$response" != "y" ]; then
        exit 0
    fi
fi

echo ""
echo "📦 Instalando dependencias base..."

# Instalar dependencias base
pip install -q -r requirements.txt

echo "✅ Dependencias base instaladas"
echo ""

# Instalar Unsloth
echo "🚀 Instalando Unsloth (esto puede tardar varios minutos)..."
echo ""

pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

if [ $? -eq 0 ]; then
    echo "✅ Unsloth instalado correctamente"
else
    echo "❌ Error al instalar Unsloth"
    echo "   Intenta instalar manualmente:"
    echo "   pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\""
    exit 1
fi

echo ""
echo "📁 Creando estructura de directorios..."

# Crear directorios necesarios
mkdir -p exports/personality
mkdir -p exports/episodic
mkdir -p lora_adapters/episodic
mkdir -p models/merged
mkdir -p models/gguf
mkdir -p models/deployments
mkdir -p validation_reports
mkdir -p logs

echo "✅ Directorios creados"
echo ""

# Verificar Ollama
echo "🦙 Verificando Ollama..."

if command -v ollama &> /dev/null; then
    echo "✅ Ollama instalado"

    # Verificar que está corriendo
    if ollama list &> /dev/null; then
        echo "✅ Ollama está corriendo"
    else
        echo "⚠️  Ollama no está corriendo"
        echo "   Inicia Ollama con: ollama serve"
    fi
else
    echo "⚠️  Ollama no está instalado"
    echo "   Descarga desde: https://ollama.ai"
    echo "   El deployment a Ollama no funcionará sin esto"
fi

echo ""
echo "=" * 60
echo "✅ CONFIGURACIÓN COMPLETADA"
echo "=" * 60
echo ""
echo "📋 PRÓXIMOS PASOS:"
echo ""
echo "1. Iniciar Memory Service:"
echo "   docker-compose up -d"
echo "   python src/main.py"
echo ""
echo "2. Capturar interacciones (desde conversation-service)"
echo ""
echo "3. Cuando tengas suficientes datos (>500 ejemplos):"
echo "   cd scripts"
echo "   python export_training_data.py --type personality"
echo "   python train_personality_lora.py --dataset ../exports/personality/*.jsonl"
echo ""
echo "4. Ver workflow completo en: TRAINING_WORKFLOW.md"
echo ""
echo "🎓 ¡Listo para entrenar!"
