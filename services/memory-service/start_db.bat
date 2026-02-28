@echo off
setlocal
set "SERVICE_DIR=%~dp0"

echo [memory-db] Verificando que Docker Desktop esté corriendo...
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker no está disponible. Abre Docker Desktop y vuelve a intentarlo.
    pause & exit /b 1
)

echo [memory-db] Levantando PostgreSQL con pgvector...
cd /D "%SERVICE_DIR%"
docker compose up -d memory-postgres

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al levantar el contenedor.
    pause & exit /b 1
)

echo.
echo [memory-db] Esperando a que PostgreSQL esté listo...
:wait_loop
docker compose exec memory-postgres pg_isready -U memory_user -d casiopy_memory >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_loop
)

echo [memory-db] PostgreSQL listo en localhost:8821
echo    Usuario  : memory_user
echo    Base     : casiopy_memory
echo    Puerto   : 8821
echo.
