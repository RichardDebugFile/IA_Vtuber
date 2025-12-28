#!/usr/bin/env pwsh
# Monitoring Service - Arranque Rápido PowerShell
# Puerto: 8900

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Monitoring Service - Iniciando" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar directorio
if (-not (Test-Path "src\main.py")) {
    Write-Host "ERROR: No se encuentra src\main.py" -ForegroundColor Red
    Write-Host "Asegúrate de ejecutar este script desde services\monitoring-service\" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Verificar venv
$venvPython = "..\..\venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: No se encuentra el entorno virtual" -ForegroundColor Red
    Write-Host "Ruta esperada: $venvPython" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "[OK] Directorio correcto" -ForegroundColor Green
Write-Host "[OK] Entorno virtual encontrado" -ForegroundColor Green
Write-Host ""

Write-Host "Iniciando Monitoring Service en puerto 8900..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Accede al dashboard en:" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8900/monitoring" -ForegroundColor White
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servicio" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Ejecutar servidor
try {
    & $venvPython -m uvicorn src.main:app --host 127.0.0.1 --port 8900 --reload
}
catch {
    Write-Host ""
    Write-Host "Error al iniciar el servicio: $_" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}
