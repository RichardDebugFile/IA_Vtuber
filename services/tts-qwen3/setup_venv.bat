@echo off
:: TTS Qwen3-TTS - Setup del Venv
:: METODO PREFERIDO: copiar venv desde disco D: (ya resuelve conflictos de compatibilidad)
:: METODO ALTERNATIVO: instalar desde requirements.txt
::
:: Python base requerido: 3.12 (Python312)
:: Nota: torch 2.10.0+cu128 (UNICO entre los TTS) - requiere venv separado

setlocal
set "SERVICE_DIR=%~dp0"
set "VENV_DIR=%SERVICE_DIR%venv"
set "SRC_VENV=D:\ExperimentosPython\TTS-Google\Qwen3-TTS\venv"

echo ============================================================
echo  TTS Qwen3-TTS - Setup del Venv Local
echo ============================================================

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [OK] Venv ya existe en %VENV_DIR%
    pause & exit /b 0
)

:: ---- METODO 1: Copiar desde disco D: (recomendado) ----
if exist "%SRC_VENV%\Scripts\python.exe" (
    echo Copiando venv desde disco D: (~5 GB, puede tardar 1 min)...
    robocopy "%SRC_VENV%" "%VENV_DIR%" /E /MT:8 /NP /NFL /NDL
    if %errorlevel% leq 7 (
        echo [OK] Setup completado via copia de venv.
        pause & exit /b 0
    ) else (
        echo [WARN] Error en copia. Intentando metodo alternativo...
    )
)

:: ---- METODO 2: Instalar desde requirements.txt ----
echo [ALTERNATIVO] Instalando desde requirements.txt...
set "PYTHON3=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON3%" ( echo [ERROR] Python 3.12 no encontrado. & pause & exit /b 1 )

"%PYTHON3%" -m venv "%VENV_DIR%"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

"%PYTHON%" -m pip install --upgrade pip --quiet
:: IMPORTANTE: torch 2.10.0+cu128 (version especifica para Qwen3-TTS)
"%PIP%" install -r "%SERVICE_DIR%requirements.txt" --extra-index-url https://download.pytorch.org/whl/cu128 --quiet

echo [OK] Setup completado.
pause
