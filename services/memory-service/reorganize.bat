@echo off
REM Script de reorganización completa de memory-service
REM Organiza archivos en estructura profesional

cd /d "F:\Documentos F\GitHub\IA_Vtuber\services\memory-service"

echo ============================================================
echo REORGANIZACION DE MEMORY-SERVICE
echo ============================================================
echo.
echo Este script creara una estructura profesional:
echo   - docs/ - Toda la documentacion
echo   - scripts/setup/ - Scripts de configuracion
echo   - scripts/backup/ - Scripts de backup
echo   - scripts/deploy/ - Scripts de despliegue
echo   - Raiz limpia con solo archivos esenciales
echo.
pause

REM ============================================================
REM PASO 1: Crear estructura de directorios
REM ============================================================
echo.
echo [1/5] Creando estructura de directorios...

mkdir "docs" 2>nul
mkdir "scripts\setup" 2>nul
mkdir "scripts\backup" 2>nul
mkdir "scripts\deploy" 2>nul

echo    ^> Directorios creados

REM ============================================================
REM PASO 2: Mover documentacion a docs/
REM ============================================================
echo.
echo [2/5] Organizando documentacion...

move /Y "PROJECT_SUMMARY.md" "docs\" 2>nul
move /Y "INSTALLATION_GUIDE.md" "docs\" 2>nul
move /Y "TRAINING_DASHBOARD_SUMMARY.md" "docs\" 2>nul
move /Y "TRAINING_WORKFLOW.md" "docs\" 2>nul
move /Y "STRUCTURE.md" "docs\" 2>nul

REM Eliminar documentacion obsoleta
del /f /q "TRAINING_SETUP_COMPLETE.md" 2>nul

echo    ^> Documentacion organizada en docs/

REM ============================================================
REM PASO 3: Mover scripts de setup
REM ============================================================
echo.
echo [3/5] Organizando scripts de setup...

move /Y "activate_training_env.bat" "scripts\setup\" 2>nul
move /Y "setup_training.bat" "scripts\setup\" 2>nul
move /Y "setup_training.sh" "scripts\setup\" 2>nul
move /Y "setup_training_env.bat" "scripts\setup\" 2>nul
move /Y "start.bat" "scripts\setup\" 2>nul
move /Y "start.sh" "scripts\setup\" 2>nul
move /Y "start_services.sh" "scripts\setup\" 2>nul

echo    ^> Scripts de setup movidos a scripts/setup/

REM ============================================================
REM PASO 4: Mover scripts de backup
REM ============================================================
echo.
echo [4/5] Organizando scripts de backup...

move /Y "backup_daily.sh" "scripts\backup\" 2>nul
move /Y "backup_weekly.sh" "scripts\backup\" 2>nul
move /Y "restore_backup.sh" "scripts\backup\" 2>nul

echo    ^> Scripts de backup movidos a scripts/backup/

REM ============================================================
REM PASO 5: Eliminar archivos basura
REM ============================================================
echo.
echo [5/5] Eliminando archivos basura...

del /f /q "nul" 2>nul
del /f /q "=0.13.0" 2>nul
del /f /q "build.log" 2>nul

echo    ^> Archivos basura eliminados

REM ============================================================
REM LIMPIEZA ADICIONAL (del script anterior)
REM ============================================================
echo.
echo [BONUS] Ejecutando limpieza de archivos obsoletos...

REM Eliminar .venv_training
rmdir /s /q ".venv_training" 2>nul

REM Eliminar modelos antiguos (2.68 GB)
rmdir /s /q "models\lora_adapters\personality_v1_20251230_002032" 2>nul
rmdir /s /q "models\lora_adapters\personality_v1_20251230_025051" 2>nul
rmdir /s /q "models\lora_adapters\personality_v1_20251230_034804" 2>nul

REM Eliminar caches de Unsloth
rmdir /s /q "unsloth_compiled_cache" 2>nul
rmdir /s /q "frontend\unsloth_compiled_cache" 2>nul
rmdir /s /q "scripts\unsloth_compiled_cache" 2>nul

REM Eliminar logs antiguos
del /f /q "logs\training_20251229_*.log" 2>nul
del /f /q "logs\training_20251230_001546.log" 2>nul
del /f /q "logs\training_v2.log" 2>nul
del /f /q "logs\training_v3.log" 2>nul

REM Eliminar exports antiguos
del /f /q "exports\personality\v0_development\casiopy_personality_initial_20251228_205308.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_initial_20251228_210033.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_initial_20251228_210107.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_213315.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_213523.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_213659.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_213720.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_213819.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_214820.jsonl" 2>nul
del /f /q "exports\personality\v0_development\casiopy_personality_natural_20251228_215822.jsonl" 2>nul

echo    ^> Limpieza completada (~2.7 GB liberados)

echo.
echo ============================================================
echo REORGANIZACION COMPLETADA
echo ============================================================
echo.
echo Estructura final:
echo   memory-service/
echo   ├── docs/               # Toda la documentacion
echo   ├── scripts/
echo   │   ├── setup/         # Scripts de configuracion
echo   │   ├── backup/        # Scripts de backup
echo   │   └── *.py           # Scripts de entrenamiento
echo   ├── frontend/          # Dashboards web
echo   ├── models/            # Solo modelo actual
echo   ├── exports/           # Datasets limpios
echo   ├── logs/              # Logs actuales
echo   └── [archivos raiz]    # Solo esenciales
echo.
echo Archivos en raiz (limpios):
echo   - README.md
echo   - .dockerignore, .env, .gitignore
echo   - docker-compose.yml, Dockerfile.training
echo   - requirements*.txt
echo   - cleanup.bat, reorganize.bat
echo.
echo Espacio liberado: ~2.7 GB
echo.
pause
