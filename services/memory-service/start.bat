@echo off
setlocal
set "SERVICE_DIR=%~dp0"
set "PYTHON=%SERVICE_DIR%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Venv no encontrado. Ejecuta setup_venv.bat primero.
    pause & exit /b 1
)

echo [memory-service] Iniciando API en http://127.0.0.1:8820 ...
cd /D "%SERVICE_DIR%src"
"%PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8820 --reload
