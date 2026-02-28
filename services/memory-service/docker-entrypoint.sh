#!/bin/bash
# ============================================================
# Docker Entrypoint para Entrenamiento de LoRA
# ============================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "  CASIOPY TRAINING ENVIRONMENT"
echo "============================================================"
echo ""

# Verificar GPU
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} GPU detectada:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo -e "${YELLOW}[WARNING]${NC} GPU no detectada - El entrenamiento sera muy lento"
fi

echo ""
echo "============================================================"
echo ""

# Comandos disponibles
case "$1" in
    dashboard)
        echo "[INFO] Iniciando Training Dashboard..."
        echo "[INFO] Dashboard disponible en: http://localhost:5000"
        echo ""
        cd /workspace/frontend
        exec python3 app.py
        ;;

    train)
        shift  # Remover 'train' de los argumentos
        echo "[INFO] Iniciando entrenamiento de LoRA..."
        echo "[INFO] Argumentos: $@"
        echo ""
        cd /workspace
        exec python3 scripts/train_personality_lora.py "$@"
        ;;

    validate)
        echo "[INFO] Validando dataset..."
        echo ""
        cd /workspace
        exec python3 scripts/validate_dataset.py
        ;;

    bash|shell|sh)
        echo "[INFO] Iniciando shell interactivo..."
        echo ""
        echo "Comandos disponibles:"
        echo "  - Dashboard:  cd frontend && python3 app.py"
        echo "  - Entrenar:   python3 scripts/train_personality_lora.py --dataset ..."
        echo "  - Validar:    python3 scripts/validate_dataset.py"
        echo ""
        exec /bin/bash
        ;;

    *)
        echo "[INFO] Comando personalizado: $@"
        exec "$@"
        ;;
esac
