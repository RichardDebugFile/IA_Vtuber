@echo off
echo ================================================
echo   CASIOPY TRAINING DASHBOARD
echo ================================================
echo.

cd /d "%~dp0\.."

REM Verificar si existe el venv de entrenamiento
if exist ".venv_training\Scripts\python.exe" (
    echo [INFO] Usando entorno virtual de entrenamiento
    set PYTHON_CMD=.venv_training\Scripts\python.exe
) else (
    echo [INFO] Usando Python del sistema
    echo [NOTA] Para un entorno aislado, ejecuta: setup_training_env.bat
    set PYTHON_CMD=python
)

echo.
echo Iniciando servidor...
echo.
echo Dashboard disponible en: http://localhost:5000
echo.
echo Presiona Ctrl+C para detener el servidor
echo ================================================
echo.

cd frontend
%PYTHON_CMD% app.py

pause
