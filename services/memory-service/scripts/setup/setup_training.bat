@echo off
REM ============================================================
REM SETUP DE ENTRENAMIENTO - CASIOPY MEMORY SERVICE (Windows)
REM ============================================================

echo 🎓 Configurando entorno de entrenamiento para Casiopy...
echo.

REM Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python no está instalado
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% detectado

REM Verificar CUDA
nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GPU detectada
    nvidia-smi --query-gpu=name --format=csv,noheader
) else (
    echo ⚠️  ADVERTENCIA: nvidia-smi no encontrado
    echo    Entrenamiento será MUY lento sin GPU
    set /p response="¿Continuar de todos modos? [y/N]: "
    if /i not "%response%"=="y" exit /b 0
)

echo.
echo 📦 Instalando dependencias base...

pip install -q -r requirements.txt

if %errorlevel% equ 0 (
    echo ✅ Dependencias base instaladas
) else (
    echo ❌ Error al instalar dependencias
    exit /b 1
)

echo.
echo 🚀 Instalando Unsloth (esto puede tardar varios minutos)...
echo.

pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

if %errorlevel% equ 0 (
    echo ✅ Unsloth instalado correctamente
) else (
    echo ❌ Error al instalar Unsloth
    echo    Intenta instalar manualmente:
    echo    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    exit /b 1
)

echo.
echo 📁 Creando estructura de directorios...

if not exist exports\personality mkdir exports\personality
if not exist exports\episodic mkdir exports\episodic
if not exist lora_adapters\episodic mkdir lora_adapters\episodic
if not exist models\merged mkdir models\merged
if not exist models\gguf mkdir models\gguf
if not exist models\deployments mkdir models\deployments
if not exist validation_reports mkdir validation_reports
if not exist logs mkdir logs

echo ✅ Directorios creados
echo.

REM Verificar Ollama
echo 🦙 Verificando Ollama...

ollama list >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Ollama instalado y corriendo
) else (
    where ollama >nul 2>&1
    if %errorlevel% equ 0 (
        echo ⚠️  Ollama instalado pero no está corriendo
        echo    Inicia Ollama con: ollama serve
    ) else (
        echo ⚠️  Ollama no está instalado
        echo    Descarga desde: https://ollama.ai
        echo    El deployment a Ollama no funcionará sin esto
    )
)

echo.
echo ============================================================
echo ✅ CONFIGURACIÓN COMPLETADA
echo ============================================================
echo.
echo 📋 PRÓXIMOS PASOS:
echo.
echo 1. Iniciar Memory Service:
echo    docker-compose up -d
echo    python src\main.py
echo.
echo 2. Capturar interacciones (desde conversation-service)
echo.
echo 3. Cuando tengas suficientes datos (^>500 ejemplos):
echo    cd scripts
echo    python export_training_data.py --type personality
echo    python train_personality_lora.py --dataset ..\exports\personality\*.jsonl
echo.
echo 4. Ver workflow completo en: TRAINING_WORKFLOW.md
echo.
echo 🎓 ¡Listo para entrenar!
