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
echo Accede al dashboard con control completo:
echo   http://127.0.0.1:8900/monitoring
echo.
echo IMPORTANTE: Usa /monitoring (no la raíz)
echo            Ahí están los botones de Start/Stop/Restart
echo.
echo Presiona Ctrl+C para detener el servicio
echo ========================================
echo.

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Ejecutar el servidor en segundo plano y abrir navegador
start /B "Monitoring Service" "..\..\venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8900

REM Esperar 3 segundos para que el servidor inicie
timeout /t 3 /nobreak >nul

REM Abrir navegador en el dashboard de monitoring
start http://127.0.0.1:8900/monitoring

echo.
echo Servidor iniciado y navegador abierto
echo Presiona cualquier tecla para detener el servidor...
pause >nul

REM Detener el servidor al cerrar
powershell -Command "Get-NetTCPConnection -LocalPort 8900 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
