@echo off
setlocal enabledelayedexpansion
cd /D "%~dp0"

REM ── Variables ─────────────────────────────────────────────────────────────
set "VENV_PY=%~dp0..\venv\Scripts\python.exe"
set "MONITORING_DIR=%~dp0..\services\monitoring-service"
set "MEMORY_DIR=%~dp0..\services\memory-service"
set "APP_URL=http://127.0.0.1:8830"
set "PYTHONUNBUFFERED=1"

REM Cargar .env si existe (ignora lineas comentadas con #)
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
)

echo ============================================
echo   Casiopy VTuber Beta -- Inicio
echo ============================================

REM ── 0. Verificar Docker y memoria-postgres ────────────────────────────────
echo [0/2] Verificando Docker y base de datos de memoria...

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   [Docker] Docker no esta activo o no esta instalado. Saltando memory-postgres.
    goto docker_skip
)

REM Verificar si el contenedor casiopy-memory-db ya esta corriendo
for /f "delims=" %%S in ('docker inspect --format "{{.State.Running}}" casiopy-memory-db 2^>nul') do set "DB_RUNNING=%%S"

if "!DB_RUNNING!"=="true" (
    echo   [Docker] memory-postgres ya activo ^(casiopy-memory-db^).
    goto docker_skip
)

echo   [Docker] Iniciando memory-postgres ^(docker compose up -d^)...
cd /D "%MEMORY_DIR%"
docker compose up -d memory-postgres
if %errorlevel% neq 0 (
    echo   [Docker] AVISO: no se pudo iniciar memory-postgres. Continuando sin memoria persistente.
)
cd /D "%~dp0"

:docker_skip

REM Verificar que el venv exista
if not exist "%VENV_PY%" (
    echo ERROR: No se encontro Python en:
    echo   %VENV_PY%
    echo Ejecuta este script desde la raiz del proyecto.
    pause
    exit /b 1
)

REM ── 1. Monitoring-service (8900) ─────────────────────────────────────────
echo [1/2] Iniciando monitoring-service...

REM Siempre cerramos la instancia anterior (si existe) para que el codigo actualizado se aplique.
REM Stop-Process -Force es seguro: solo mata el proceso Python en ese puerto.
powershell -NoProfile -Command ^
  "Get-NetTCPConnection -LocalPort 8900 -State Listen -ErrorAction SilentlyContinue ^| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul

REM Iniciar monitoring en background (ventana oculta)
powershell -NoProfile -Command ^
  "Start-Process -FilePath '%VENV_PY%' -ArgumentList @('-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8900') -WorkingDirectory '%MONITORING_DIR%' -WindowStyle Hidden"

set intentos=0
:esperar_monitoring
    timeout /t 1 /nobreak >nul
    set /a intentos+=1
    powershell -NoProfile -Command "try{$null=(New-Object Net.Sockets.TcpClient('127.0.0.1',8900));exit 0}catch{exit 1}" >nul 2>&1
    if %errorlevel%==0 goto monitoring_listo
    if !intentos! lss 20 goto esperar_monitoring

echo ERROR: monitoring-service no respondio en 20 segundos.
echo Comprueba que el venv tenga uvicorn y fastapi instalados.
pause
exit /b 1

:monitoring_listo
echo       monitoring-service listo.

REM ── 2. Casiopy App (8830) ────────────────────────────────────────────────
echo [2/2] Iniciando Casiopy App en %APP_URL% ...
echo.

REM Abrir el navegador automaticamente tras 4 s (en background, sin bloquear)
start /B powershell -NoProfile -Command "Start-Sleep 4; Start-Process '%APP_URL%'"

REM Iniciar casiopy-app (modo foreground — esta ventana muestra los logs)
"%VENV_PY%" -m uvicorn server:app --host 127.0.0.1 --port 8830
pause
