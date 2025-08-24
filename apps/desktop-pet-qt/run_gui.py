# Ejecuta la app QT desde cualquier cwd (evita líos de rutas con Honcho/Make)
import os, sys, subprocess

ROOT = os.path.dirname(os.path.dirname(__file__))            # apps/desktop-pet-qt
SRC  = os.path.join(ROOT, "src")
# Lanza "python main.py" con cwd=src para que assets y rutas relativas funcionen
subprocess.call([sys.executable, "main.py"], cwd=SRC)
