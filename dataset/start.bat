@echo off
REM Dataset Generator - Launch Script
REM Puerto: 8801

echo ========================================
echo  Dataset Generator - Iniciando
echo ========================================
echo.

REM Verificar que estamos en el directorio correcto
if not exist "src\main.py" (
    echo ERROR: No se encuentra src\main.py
    echo Asegurate de ejecutar este script desde dataset\
    pause
    exit /b 1
)

REM Verificar que el venv existe
if not exist "..\venv\Scripts\python.exe" (
    echo ERROR: No se encuentra el entorno virtual en ..\venv\
    echo Ejecuta primero: python -m venv ..\venv
    pause
    exit /b 1
)

echo [OK] Directorio correcto
echo [OK] Entorno virtual encontrado
echo.

REM Verificar si metadata.csv existe
if not exist "metadata.csv" (
    echo AVISO: No se encuentra metadata.csv
    echo Generando dataset de 2000 clips...
    echo.
    "..\venv\Scripts\python.exe" generate_metadata.py
    echo.
    echo [OK] Metadata generado
    echo.
)

REM Verificar que el directorio wavs existe
if not exist "wavs" (
    echo Creando directorio wavs\
    mkdir wavs
)

echo Iniciando Dataset Generator en puerto 8801...
echo.
echo Accede a la interfaz web:
echo   http://127.0.0.1:8801
echo.
echo PASOS:
echo   1. Haz clic en "Inicializar Dataset" (si es la primera vez)
echo   2. Verifica que los servicios TTS y Fish esten activos
echo   3. Configura los parametros y haz clic en "Iniciar"
echo.
echo Presiona Ctrl+C para detener el servicio
echo ========================================
echo.

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Ejecutar el servidor en segundo plano y abrir navegador
start /B "Dataset Generator" "..\venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8801

REM Esperar 3 segundos para que el servidor inicie
timeout /t 3 /nobreak >nul

REM Abrir navegador
start http://127.0.0.1:8801

echo.
echo Servidor iniciado y navegador abierto
echo Presiona cualquier tecla para detener el servidor...
pause >nul

REM Detener el servidor al cerrar
powershell -Command "Get-NetTCPConnection -LocalPort 8801 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo Servidor detenido
