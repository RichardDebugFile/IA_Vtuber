#!/bin/bash
# Monitoring Service - Arranque Rápido
# Puerto: 8900

echo "========================================"
echo " Monitoring Service - Iniciando"
echo "========================================"
echo ""

# Verificar directorio
if [ ! -f "src/main.py" ]; then
    echo "ERROR: No se encuentra src/main.py"
    echo "Asegúrate de ejecutar este script desde services/monitoring-service/"
    read -p "Presiona Enter para salir"
    exit 1
fi

# Verificar venv
VENV_PYTHON="../../venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: No se encuentra el entorno virtual"
    echo "Ruta esperada: $VENV_PYTHON"
    read -p "Presiona Enter para salir"
    exit 1
fi

echo "[OK] Directorio correcto"
echo "[OK] Entorno virtual encontrado"
echo ""

echo "Iniciando Monitoring Service en puerto 8900..."
echo ""
echo "Accede al dashboard en:"
echo "  http://127.0.0.1:8900/monitoring"
echo ""
echo "Presiona Ctrl+C para detener el servicio"
echo "========================================"
echo ""

# Ejecutar servidor
$VENV_PYTHON -m uvicorn src.main:app --host 127.0.0.1 --port 8900 --reload
