@echo off
REM ============================================================
REM START SCRIPT - CASIOPY MEMORY SERVICE (Windows)
REM ============================================================

echo 🧠 Iniciando Casiopy Memory Service...
echo.

REM Verificar que existe .env
if not exist .env (
    echo ⚠️  Archivo .env no encontrado
    echo    Copiando .env.example a .env...
    copy .env.example .env
    echo    ⚠️  IMPORTANTE: Edita .env con tus configuraciones
    echo.
)

REM Iniciar PostgreSQL con Docker
echo 🐘 Iniciando PostgreSQL con Docker Compose...
docker-compose up -d

REM Esperar a que PostgreSQL esté listo
echo ⏳ Esperando a que PostgreSQL esté listo...
timeout /t 5 /nobreak > nul

REM Verificar que PostgreSQL está corriendo
docker ps | findstr casiopy-memory-db > nul
if %errorlevel% equ 0 (
    echo ✅ PostgreSQL iniciado correctamente
) else (
    echo ❌ Error: PostgreSQL no está corriendo
    echo    Ver logs: docker-compose logs memory-postgres
    exit /b 1
)

REM Crear directorio de logs si no existe
if not exist logs mkdir logs

REM Verificar que Python está instalado
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python no está instalado
    exit /b 1
)

REM Verificar dependencias Python
echo 📦 Verificando dependencias Python...
if not exist venv (
    echo    Creando entorno virtual...
    python -m venv venv
)

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Instalar/actualizar dependencias
echo    Instalando dependencias...
pip install -q -r requirements.txt

REM Iniciar el servicio
echo.
echo 🚀 Iniciando Memory Service API...
echo    URL: http://localhost:8820
echo    Docs: http://localhost:8820/docs
echo    PostgreSQL: localhost:8821
echo.

cd src
python main.py
