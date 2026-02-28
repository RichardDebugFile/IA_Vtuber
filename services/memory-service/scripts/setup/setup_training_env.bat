@echo off
REM ============================================================
REM Script de configuracion del entorno de entrenamiento
REM Crea un venv limpio con todas las dependencias necesarias
REM ============================================================

echo ============================================================
echo   CONFIGURACION DE ENTORNO DE ENTRENAMIENTO
echo   Casiopy Memory Service
echo ============================================================
echo.

cd /d "%~dp0"

REM Verificar si Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH
    echo Por favor instala Python 3.10 o superior
    pause
    exit /b 1
)

echo [1/5] Verificando Python...
python --version

REM Crear directorio para el venv si no existe
if not exist ".venv_training" (
    echo.
    echo [2/5] Creando entorno virtual...
    python -m venv .venv_training
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado
) else (
    echo.
    echo [2/5] Entorno virtual ya existe
)

REM Activar el entorno virtual
echo.
echo [3/5] Activando entorno virtual...
call .venv_training\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual
    pause
    exit /b 1
)

REM Actualizar pip
echo.
echo [4/5] Actualizando pip...
python -m pip install --upgrade pip

REM Instalar PyTorch con CUDA 12.4 (para RTX 5060 Ti)
echo.
echo [5/5] Instalando dependencias de entrenamiento...
echo.
echo [INFO] Instalando PyTorch con CUDA 12.4...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

REM Instalar Unsloth
echo.
echo [INFO] Instalando Unsloth (puede tardar varios minutos)...
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

REM Instalar dependencias adicionales
echo.
echo [INFO] Instalando dependencias adicionales...
pip install datasets transformers trl accelerate bitsandbytes

REM Instalar dependencias del dashboard
echo.
echo [INFO] Instalando dependencias del dashboard...
pip install -r frontend\requirements.txt

REM Verificar instalacion
echo.
echo ============================================================
echo   VERIFICACION DE INSTALACION
echo ============================================================
echo.

python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torch; print(f'CUDA disponible: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

echo.
echo ============================================================
echo   INSTALACION COMPLETADA
echo ============================================================
echo.
echo Para usar el entorno de entrenamiento:
echo   1. Ejecuta: activate_training_env.bat
echo   2. Inicia el dashboard: cd frontend ^&^& python app.py
echo   3. O entrena directamente: python scripts\train_personality_lora.py --dataset ...
echo.
echo El entorno esta en: .venv_training\
echo.

pause
