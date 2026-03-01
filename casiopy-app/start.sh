#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -f .env ] && export $(grep -v '^#' .env | xargs)

VENV_PY="../venv/bin/python"

echo "============================================"
echo "  Casiopy VTuber Beta — Inicio"
echo "============================================"

# ── 1. Monitoring-service (8900) ─────────────────────────────────────────
if nc -z 127.0.0.1 8900 2>/dev/null; then
    echo "[1/2] monitoring-service ya está activo."
else
    echo "[1/2] Iniciando monitoring-service (puerto 8900)..."
    pushd ../services/monitoring-service >/dev/null
    PYTHONUNBUFFERED=1 "$OLDPWD/$VENV_PY" -m uvicorn src.main:app \
        --host 127.0.0.1 --port 8900 &
    popd >/dev/null

    intentos=0
    until nc -z 127.0.0.1 8900 2>/dev/null; do
        sleep 1
        intentos=$((intentos+1))
        if [ "$intentos" -ge 20 ]; then
            echo "ERROR: monitoring-service no respondió en 20s."
            exit 1
        fi
    done
    echo "      monitoring-service listo."
fi

# ── 2. Casiopy App (8830) ───────────────────────────────────────────────
echo "[2/2] Iniciando Casiopy App en http://127.0.0.1:8830 ..."
echo "      Abre el navegador en esa URL y pulsa 'Iniciar servicios'."
echo ""
PYTHONUNBUFFERED=1 $VENV_PY -m uvicorn server:app --host 127.0.0.1 --port 8830
