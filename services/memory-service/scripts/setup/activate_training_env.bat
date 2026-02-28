@echo off
REM ============================================================
REM Script para activar el entorno de entrenamiento
REM ============================================================

cd /d "%~dp0"

if not exist ".venv_training\Scripts\activate.bat" (
    echo [ERROR] Entorno virtual no encontrado
    echo Por favor ejecuta primero: setup_training_env.bat
    pause
    exit /b 1
)

echo [INFO] Activando entorno de entrenamiento...
call .venv_training\Scripts\activate.bat

echo.
echo ============================================================
echo   ENTORNO DE ENTRENAMIENTO ACTIVADO
echo ============================================================
echo.
echo Comandos disponibles:
echo   - Iniciar dashboard:  cd frontend ^&^& python app.py
echo   - Entrenar LoRA:      python scripts\train_personality_lora.py --dataset ...
echo   - Validar dataset:    python scripts\validate_dataset.py
echo.
echo Para salir: deactivate
echo.

REM Mantener la consola abierta
cmd /k
