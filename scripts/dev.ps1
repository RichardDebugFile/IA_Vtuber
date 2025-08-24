param([switch]$Kill)

# Ruta repo (carpeta raíz)
$Root = Split-Path -Parent $PSScriptRoot

# Activa venv
$venv = Join-Path $Root "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }

# Carga .env (simple) si existe en raíz
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*$') { return }
    $kv = $_.Split('=',2)
    if ($kv.Length -eq 2) { $name=$kv[0].Trim(); $value=$kv[1].Trim(); Set-Item -Path "env:$name" -Value $value }
  }
}

if ($Kill) {
  Get-Job -Name gw,conv -ErrorAction SilentlyContinue | Stop-Job -Force
  Get-Job -Name gw,conv -ErrorAction SilentlyContinue | Remove-Job
  Write-Host "Jobs gw/conv detenidos."
  exit
}

# Inicia gateway
$gw = Start-Job -Name gw -ScriptBlock {
  Set-Location (Join-Path $using:Root "services\gateway")
  python -m uvicorn src.main:app --host 127.0.0.1 --port 8765 --app-dir src
}

# Inicia conversation
$cv = Start-Job -Name conv -ScriptBlock {
  Set-Location (Join-Path $using:Root "services\conversation")
  python -m uvicorn src.server:app --host 127.0.0.1 --port 8801 --app-dir src
}

Write-Host ""
Write-Host "Servicios levantados como Jobs:"
Write-Host "  gateway     -> Job Id $($gw.Id)"
Write-Host "  conversation-> Job Id $($cv.Id)"
Write-Host ""
Write-Host "Ver logs:"
Write-Host "  Receive-Job -Name gw    -Keep -Wait"
Write-Host "  Receive-Job -Name conv  -Keep -Wait"
Write-Host ""
Write-Host "Detener ambos:"
Write-Host "  .\scripts\dev.ps1 -Kill"
