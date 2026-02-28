#!/bin/bash

echo "================================================"
echo "  CASIOPY TRAINING DASHBOARD"
echo "================================================"
echo ""
echo "Iniciando servidor..."
echo ""
echo "Dashboard disponible en: http://localhost:5000"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo "================================================"
echo ""

cd "$(dirname "$0")"
python3 app.py
