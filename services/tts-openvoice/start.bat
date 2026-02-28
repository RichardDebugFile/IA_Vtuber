@echo off
:: TTS OpenVoice V2 - Inicio Manual
:: Puerto: 8811

set PYTHON=%~dp0venv\Scripts\python.exe
set SERVER=%~dp0server.py

if not exist "%PYTHON%" (
    echo [ERROR] Venv local no encontrado. Ejecuta setup_venv.bat primero.
    pause
    exit /b 1
)

echo Iniciando TTS OpenVoice V2 en http://127.0.0.1:8811
"%PYTHON%" "%SERVER%"
