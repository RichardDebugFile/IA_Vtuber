@echo off
REM Monitoring Service - Arranque Rapido
REM Puerto: 8900

echo ========================================
echo  Monitoring Service - Iniciando
echo ========================================
echo.

REM Verificar que estamos en el directorio correcto
if not exist "src\main.py" (
    echo ERROR: No se encuentra src\main.py
    echo Asegurate de ejecutar este script desde services\monitoring-service\
    pause
    exit /b 1
)

REM Verificar que el venv existe
if not exist "..\..\venv\Scripts\python.exe" (
    echo ERROR: No se encuentra el entorno virtual en ..\..\venv\
    echo Ejecuta primero: python -m venv venv
    pause
    exit /b 1
)

echo [OK] Directorio correcto
echo [OK] Entorno virtual encontrado
echo.

REM Activar venv y arrancar el servicio
echo Iniciando Monitoring Service en puerto 8900...
echo.
echo Accede al dashboard en:
echo   http://127.0.0.1:8900/monitoring
echo.
echo Presiona Ctrl+C para detener el servicio
echo ========================================
echo.

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Ejecutar el servidor
"..\..\venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8900 --reload

pause
