@echo off
setlocal
cd /D "%~dp0"

REM Cargar .env si existe
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do set %%a=%%b
)
set PYTHONUNBUFFERED=1
set VENV_PY=%~dp0..\venv\Scripts\python.exe

echo ============================================
echo   Casiopy VTuber Beta — Inicio
echo ============================================

REM ── 1. Monitoring-service (8900) ─────────────────────────────────────────
powershell -NoProfile -Command ^
  "try{$null=(New-Object Net.Sockets.TcpClient('127.0.0.1',8900));exit 0}catch{exit 1}" ^
  >nul 2>&1
if %errorlevel%==0 (
    echo [1/2] monitoring-service ya esta activo.
) else (
    echo [1/2] Iniciando monitoring-service ^(puerto 8900^)...
    start /B cmd /c "cd /D "%~dp0..\services\monitoring-service" && "%VENV_PY%" -m uvicorn src.main:app --host 127.0.0.1 --port 8900"

    set /a intentos=0
    :esperar_monitoring
    timeout /t 1 /nobreak >nul
    set /a intentos+=1
    powershell -NoProfile -Command ^
      "try{$null=(New-Object Net.Sockets.TcpClient('127.0.0.1',8900));exit 0}catch{exit 1}" ^
      >nul 2>&1
    if %errorlevel%==0 goto monitoring_listo
    if %intentos% lss 20 goto esperar_monitoring
    echo ERROR: monitoring-service no respondio en 20s. Revisa el log.
    pause & exit /b 1
    :monitoring_listo
    echo       monitoring-service listo.
)

REM ── 2. Casiopy App (8830) ────────────────────────────────────────────────
echo [2/2] Iniciando Casiopy App en http://127.0.0.1:8830 ...
echo       Abre el navegador en esa URL y pulsa "Iniciar servicios".
echo.
"%VENV_PY%" -m uvicorn server:app --host 127.0.0.1 --port 8830
pause
