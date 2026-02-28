#!/bin/bash
# Iniciar ambos servicios: Dashboard de entrenamiento y Chat

cd /workspace/frontend

# Iniciar dashboard de entrenamiento en background (puerto 5000)
python3 app.py &

# Esperar un momento
sleep 2

# Iniciar chat (puerto 5001)
python3 chat_app.py
