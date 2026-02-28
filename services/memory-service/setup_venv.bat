@echo off
setlocal
set "SERVICE_DIR=%~dp0"

echo [memory-service] Creando entorno virtual...
python -m venv "%SERVICE_DIR%venv"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se pudo crear el venv. Verifica que Python 3.10+ está en el PATH.
    pause & exit /b 1
)

echo [memory-service] Actualizando pip...
"%SERVICE_DIR%venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo [memory-service] Instalando dependencias API (requirements-api.txt)...
"%SERVICE_DIR%venv\Scripts\pip.exe" install -r "%SERVICE_DIR%requirements-api.txt"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al instalar dependencias.
    pause & exit /b 1
)

echo.
echo [memory-service] Setup completado.
echo    Python : %SERVICE_DIR%venv\Scripts\python.exe
echo    Puerto : 8820 (API)  /  8821 (PostgreSQL via Docker)
echo.
echo Para iniciar la base de datos:  start_db.bat
echo Para iniciar la API:            start.bat
echo.
pause
