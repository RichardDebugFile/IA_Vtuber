@echo off
setlocal
set "SERVICE_DIR=%~dp0"
set "PYTHON=%SERVICE_DIR%venv\Scripts\python.exe"
set "PIP=%SERVICE_DIR%venv\Scripts\pip.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Venv no encontrado. Ejecuta setup_venv.bat primero.
    pause & exit /b 1
)

echo [memory-tests] Instalando pytest si falta...
"%PIP%" install pytest --quiet

echo.
echo [memory-tests] REQUISITO: El servicio debe estar corriendo:
echo   1. start_db.bat  (PostgreSQL en localhost:8821)
echo   2. start.bat     (API en http://127.0.0.1:8820)
echo.

cd /D "%SERVICE_DIR%"
"%PYTHON%" -m pytest tests/ -v --tb=short %*

echo.
if %ERRORLEVEL% equ 0 (
    echo [OK] Todos los tests pasaron.
) else (
    echo [FAIL] Algunos tests fallaron. Ver salida arriba.
)
pause
