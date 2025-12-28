# Ejecuta la app QT desde cualquier cwd (evita líos de rutas con Honcho/Make)
import os, sys, subprocess

# Ruta al directorio del servicio (services/face-service-2D-simple)
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(ROOT, "src")
# Lanza "python main.py" con cwd=src para que assets y rutas relativas funcionen
subprocess.call([sys.executable, "main.py"], cwd=SRC)
