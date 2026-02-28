@echo off
REM Script de limpieza para memory-service
REM Elimina archivos obsoletos y libera ~2.7 GB

echo ============================================================
echo LIMPIEZA DE MEMORY-SERVICE
echo ============================================================
echo.
echo Este script eliminara archivos obsoletos (~2.7 GB):
echo   - 3 modelos LoRA antiguos (2.68 GB)
echo   - .venv_training corrupto
echo   - 3 caches de Unsloth duplicados
echo   - Logs antiguos
echo   - Archivos basura
echo.
echo MANTENDRA:
echo   - personality_v2_refined_20251230_163256 (modelo actual)
echo   - refine_v3.log, resume_v3.log (logs actuales)
echo   - Exports v1 y v2 (produccion)
echo.
pause

cd /d "F:\Documentos F\GitHub\IA_Vtuber\services\memory-service"

echo.
echo [1/6] Eliminando archivos basura en raiz...
del /f /q "nul" 2>nul
del /f /q "=0.13.0" 2>nul
del /f /q "build.log" 2>nul
echo    ^> Listo

echo.
echo [2/6] Eliminando .venv_training corrupto...
rmdir /s /q ".venv_training" 2>nul
echo    ^> Listo

echo.
echo [3/6] Eliminando modelos LoRA antiguos (2.68 GB)...
rmdir /s /q "models\lora_adapters\personality_v1_20251230_002032" 2>nul
rmdir /s /q "models\lora_adapters\personality_v1_20251230_025051" 2>nul
rmdir /s /q "models\lora_adapters\personality_v1_20251230_034804" 2>nul
echo    ^> Listo - 2.68 GB liberados

echo.
echo [4/6] Eliminando caches de Unsloth duplicados...
rmdir /s /q "unsloth_compiled_cache" 2>nul
rmdir /s /q "frontend\unsloth_compiled_cache" 2>nul
rmdir /s /q "scripts\unsloth_compiled_cache" 2>nul
echo    ^> Listo

echo.
echo [5/6] Eliminando logs antiguos...
del /f /q "logs\training_20251229_*.log" 2>nul
del /f /q "logs\training_20251230_001546.log" 2>nul
del /f /q "logs\training_v2.log" 2>nul
del /f /q "logs\training_v3.log" 2>nul
echo    ^> Listo

echo.
echo [6/6] Eliminando exports de desarrollo antiguos...
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
echo    ^> Listo

echo.
echo ============================================================
echo LIMPIEZA COMPLETADA
echo ============================================================
echo.
echo Espacio liberado: ~2.7 GB
echo.
echo Archivos MANTENIDOS:
echo   - models\lora_adapters\personality_v2_refined_20251230_163256\
echo   - logs\refine_v3.log
echo   - logs\resume_v3.log
echo   - exports\personality\v1_production\
echo   - exports\personality\v2_improved\
echo.
pause
