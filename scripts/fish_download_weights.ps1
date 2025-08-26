param(
  [string]$ModelDir = "services/voice/checkpoints/openaudio-s1-mini"
)
Write-Host "Descargando pesos de OpenAudio S1 mini a $ModelDir"
huggingface-cli download fishaudio/openaudio-s1-mini --local-dir $ModelDir
Write-Host "Listo."
