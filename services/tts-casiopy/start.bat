@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%..\tts-openvoice\venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Venv de tts-openvoice no encontrado: %PYTHON%
    echo        Ejecuta setup_venv.bat en services\tts-openvoice\
    pause
    exit /b 1
)

echo [tts-casiopy] Iniciando en http://127.0.0.1:8815 ...
"%PYTHON%" "%SCRIPT_DIR%server.py"
