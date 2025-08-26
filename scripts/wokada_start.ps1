Param([string]$Port = $env:WOKADA_PORT)
if (-not $Port) { $Port = "18888" }

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$wk   = Join-Path $root "third_party\wokada"

if (-not (Test-Path $wk)) {
  Write-Error "[wokada] Falta third_party\wokada"
  exit 1
}

$exe = Join-Path $wk "MMVCServerSIO.exe"
if (Test-Path $exe) {
  Write-Host "[wokada] Ejecutando EXE en puerto $Port (foreground)..."
  & $exe -p $Port --https false
  exit $LASTEXITCODE
}

$pyServer = Join-Path $wk "server\server.py"
if (Test-Path $pyServer) {
  Write-Host "[wokada] No hay EXE; usando servidor Python (foreground)..."
  Push-Location (Split-Path $pyServer)
  & $env:VIRTUAL_ENV\Scripts\python.exe .\server.py -p $Port --https false
  $code = $LASTEXITCODE
  Pop-Location
  exit $code
}

Write-Error "[wokada] Ni EXE ni server.py encontrados."
exit 1
