@echo off
:: TTS Qwen3-TTS - Inicio Manual
:: Puerto: 8813

set PYTHON=%~dp0venv\Scripts\python.exe
set SERVER=%~dp0server.py

if not exist "%PYTHON%" (
    echo [ERROR] Venv local no encontrado. Ejecuta setup_venv.bat primero.
    pause
    exit /b 1
)

echo Iniciando TTS Qwen3 en http://127.0.0.1:8813
"%PYTHON%" "%SERVER%"
