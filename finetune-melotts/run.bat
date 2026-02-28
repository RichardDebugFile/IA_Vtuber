@echo off
REM ============================================================
REM  Fine-tune MeloTTS - Launcher
REM  Usa el venv de services/tts-openvoice (donde esta melo)
REM ============================================================

SET VENV=%~dp0..\services\tts-openvoice\venv\Scripts\python.exe

IF NOT EXIST "%VENV%" (
    echo [ERROR] No se encontro el venv de tts-openvoice en:
    echo         %VENV%
    echo         Asegurate de que el servicio tts-openvoice esta configurado.
    pause
    exit /b 1
)

IF "%1"=="" (
    REM Sin argumentos -> lanzar la UI web (modo recomendado)
    echo [run.bat] Iniciando interfaz web en http://127.0.0.1:8820 ...
    "%VENV%" "%~dp0service.py"
    goto :end
)

IF "%1"=="ui" (
    echo [run.bat] Iniciando interfaz web en http://127.0.0.1:8820 ...
    "%VENV%" "%~dp0service.py"
    goto :end
)

IF "%1"=="help" (
    echo.
    echo  Fine-tune MeloTTS - Launcher
    echo  ==============================
    echo  run.bat           Abrir UI web  ^(RECOMENDADO^)
    echo  run.bat ui        Igual que arriba
    echo  run.bat 1         Paso 1 manual: Preparar dataset
    echo  run.bat 2         Paso 2 manual: Fonemizar
    echo  run.bat 3         Paso 3 manual: Entrenar
    echo  run.bat 3 --resume  Reanudar entrenamiento
    echo  run.bat 4         Paso 4 manual: Probar
    echo  run.bat monitor   Abrir TensorBoard
    echo  run.bat help      Ver esta ayuda
    echo.
    pause
    exit /b 0
)

IF "%1"=="1" (
    echo [run.bat] Ejecutando Paso 1: Preparar dataset...
    "%VENV%" "%~dp01_prepare_dataset.py" %2 %3 %4
    goto :end
)

IF "%1"=="2" (
    echo [run.bat] Ejecutando Paso 2: Fonemizar...
    "%VENV%" "%~dp02_preprocess.py" %2 %3 %4
    goto :end
)

IF "%1"=="3" (
    echo [run.bat] Ejecutando Paso 3: Entrenamiento...
    "%VENV%" "%~dp03_train.py" %2 %3 %4
    goto :end
)

IF "%1"=="4" (
    echo [run.bat] Ejecutando Paso 4: Test...
    "%VENV%" "%~dp04_test.py" %2 %3 %4
    goto :end
)

IF "%1"=="monitor" (
    echo [run.bat] Abriendo TensorBoard en http://localhost:6006
    echo           Muestra: perdida del generador, discriminador, audio generado durante train
    echo           Ctrl+C para cerrar.
    echo.
    "%VENV%" -m tensorboard.main --logdir "%~dp0logs" --host 127.0.0.1 --port 6006
    goto :end
)

IF "%1"=="all" (
    echo [run.bat] Ejecutando pasos 1 y 2 en secuencia...
    "%VENV%" "%~dp01_prepare_dataset.py"
    IF ERRORLEVEL 1 (
        echo [ERROR] Paso 1 fallo. Abortando.
        pause
        exit /b 1
    )
    "%VENV%" "%~dp02_preprocess.py"
    IF ERRORLEVEL 1 (
        echo [ERROR] Paso 2 fallo. Abortando.
        pause
        exit /b 1
    )
    echo.
    echo [run.bat] Pasos 1 y 2 completados.
    echo           Ejecuta: run.bat 3   para iniciar entrenamiento
    goto :end
)

echo [ERROR] Paso desconocido: %1
echo         Usa run.bat sin argumentos para ver la ayuda.
exit /b 1

:end
echo.
IF ERRORLEVEL 1 (
    echo [FALLO] El paso termino con error.
) ELSE (
    echo [OK] Paso completado.
)
pause
