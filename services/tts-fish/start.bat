@echo off
:: TTS Fish Speech (Local) - Inicio Manual
:: Puerto: 8814

set PYTHON=%~dp0venv\Scripts\python.exe
set SERVER=%~dp0server.py

if not exist "%PYTHON%" (
    echo [ERROR] Venv local no encontrado. Ejecuta setup_venv.bat primero.
    pause
    exit /b 1
)

echo Iniciando TTS Fish Speech (local) en http://127.0.0.1:8814
"%PYTHON%" "%SERVER%"
