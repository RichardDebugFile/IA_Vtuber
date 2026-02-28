@echo off
:: TTS OpenVoice V2 - Setup del Venv
:: METODO PREFERIDO: copiar venv desde disco D: (ya resuelve conflictos de compatibilidad)
:: METODO ALTERNATIVO: instalar desde requirements.txt
::
:: Python base requerido: 3.12 (Python312)

setlocal
set "SERVICE_DIR=%~dp0"
set "VENV_DIR=%SERVICE_DIR%venv"
set "REPO_DIR=%SERVICE_DIR%repo"
set "SRC_VENV=D:\ExperimentosPython\TTS-Google\OpenVoice-V2\venv"

echo ============================================================
echo  TTS OpenVoice V2 - Setup del Venv Local
echo ============================================================

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [OK] Venv ya existe en %VENV_DIR%
    echo      Si quieres reinstalar, elimina la carpeta 'venv' primero.
    pause & exit /b 0
)

:: ---- METODO 1: Copiar desde disco D: (recomendado) ----
if exist "%SRC_VENV%\Scripts\python.exe" (
    echo [1/2] Copiando venv desde disco D:...
    echo       Origen:  %SRC_VENV%
    echo       Destino: %VENV_DIR%
    robocopy "%SRC_VENV%" "%VENV_DIR%" /E /MT:8 /NP /NFL /NDL
    if %errorlevel% leq 7 (
        echo [2/2] Actualizando path del paquete editable openvoice...
        set "FINDER=%VENV_DIR%\Lib\site-packages\__editable___myshell_openvoice_0_0_0_finder.py"
        powershell -NoProfile -Command "(Get-Content '!FINDER!') -replace 'D:\\\\ExperimentosPython\\\\TTS-Google\\\\OpenVoice-V2\\\\OpenVoice\\\\openvoice', '%REPO_DIR:\=\\%\\OpenVoice\\openvoice' | Set-Content '!FINDER!'"
        echo [OK] Setup completado via copia de venv.
        pause & exit /b 0
    ) else (
        echo [WARN] robocopy termino con error. Intentando metodo alternativo...
    )
)

:: ---- METODO 2: Instalar desde requirements.txt ----
echo [ALTERNATIVO] Instalando desde requirements.txt...
echo Buscando Python 3.12...
set "PYTHON3=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON3%" (
    echo [ERROR] Python 3.12 no encontrado en %PYTHON3%
    echo Instala Python 3.12 desde python.org o ajusta la ruta en este script.
    pause & exit /b 1
)

echo Creando venv con Python 3.12...
"%PYTHON3%" -m venv "%VENV_DIR%"

set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

echo Actualizando pip...
"%PYTHON%" -m pip install --upgrade pip --quiet

echo Instalando dependencias (puede tardar 10-20 min)...
"%PIP%" install -r "%SERVICE_DIR%requirements.txt" --extra-index-url https://download.pytorch.org/whl/cu128 --quiet

echo Instalando openvoice como editable desde repo local...
"%PIP%" install -e "%REPO_DIR%\OpenVoice" --no-deps --quiet

echo [OK] Setup completado via requirements.txt.
pause
