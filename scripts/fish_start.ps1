# scripts\fish_start.ps1
$ErrorActionPreference = "Stop"

# Raíz del repo (esta carpeta 'scripts' cuelga de la raíz)
$root    = Split-Path -Parent $PSScriptRoot

# Python del venv 3.12 (NO tocamos tu venv 3.13)
$py312   = Join-Path $root ".venv-voice312\Scripts\python.exe"

# Carpeta del código de OpenAudio
$oaRoot  = Join-Path $root "third_party\openaudio"

# Checkpoints (openaudio-s1-mini) DENTRO de openaudio/checkpoints
$ckptDir = Join-Path $oaRoot "checkpoints\openaudio-s1-mini"
$codec   = Join-Path $ckptDir "codec.pth"

# Validaciones rápidas (mejor fallo temprano y claro)
if (-not (Test-Path $py312)) { throw "No existe $py312 (¿creaste .venv-voice312?)" }
if (-not (Test-Path $oaRoot)) { throw "No existe $oaRoot (¿clonaste/colocaste openaudio ahí?)" }
if (-not (Test-Path $ckptDir)) { throw "No existe $ckptDir (descarga los pesos ahí)" }
if (-not (Test-Path $codec)) { throw "No existe $codec (falta codec.pth en $ckptDir)" }

# Cambia directorio de trabajo a openaudio (evita rutas relativas rotas)
Set-Location $oaRoot

# Lanza el server usando RUTAS RELATIVAS desde $oaRoot
& $py312 -m tools.api_server `
  --listen 127.0.0.1:9080 `
  --llama-checkpoint-path ".\checkpoints\openaudio-s1-mini" `
  --decoder-checkpoint-path ".\checkpoints\openaudio-s1-mini\codec.pth" `
  --decoder-config-name modded_dac_vq
