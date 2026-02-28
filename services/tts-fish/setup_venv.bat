@echo off
:: TTS Fish Speech - Setup del Venv
:: METODO PREFERIDO: copiar venv desde disco D: (ya resuelve conflictos de compatibilidad)
:: METODO ALTERNATIVO: instalar desde requirements.txt
::
:: Python base requerido: 3.12 (Python312)
:: Nota: protobuf 3.19.6 e incompatibilidades con otros TTS - requiere venv separado

setlocal
set "SERVICE_DIR=%~dp0"
set "VENV_DIR=%SERVICE_DIR%venv"
set "REPO_DIR=%SERVICE_DIR%repo"
set "SRC_VENV=D:\ExperimentosPython\TTS-Google\fish-speech\venv"

echo ============================================================
echo  TTS Fish Speech - Setup del Venv Local
echo ============================================================

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [OK] Venv ya existe en %VENV_DIR%
    echo      Si quieres reinstalar, elimina la carpeta 'venv' primero.
    pause & exit /b 0
)

:: ---- METODO 1: Copiar desde disco D: (recomendado) ----
if exist "%SRC_VENV%\Scripts\python.exe" (
    echo [1/2] Copiando venv desde disco D:...
    robocopy "%SRC_VENV%" "%VENV_DIR%" /E /MT:8 /NP /NFL /NDL
    if %errorlevel% leq 7 (
        echo [2/2] Actualizando path del paquete editable fish-speech...
        set "FINDER=%VENV_DIR%\Lib\site-packages\__editable___fish_speech_0_1_0_finder.py"
        powershell -NoProfile -Command "$f='%FINDER%'; $c=(Get-Content $f -Raw); $c=$c -replace 'D:\\\\ExperimentosPython\\\\TTS-Google\\\\fish-speech','%REPO_DIR:\=\\%'; Set-Content -Path $f -Value $c -NoNewline"
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
"%PIP%" install -r "%SERVICE_DIR%requirements.txt" --extra-index-url https://download.pytorch.org/whl/cu128 --quiet
"%PIP%" install -e "%REPO_DIR%" --no-deps --quiet

echo [OK] Setup completado via requirements.txt.
pause
