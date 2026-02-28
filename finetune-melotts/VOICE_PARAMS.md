# Parámetros óptimos — voz casiopy

Encontrados experimentalmente con el Pitch Tester tras entrenar `G_24500.pth`.

## Síntesis

| Parámetro     | Valor  | Notas |
|---------------|--------|-------|
| `pitch_shift` | `+1.0` st | El modelo fine-tuneado tiende a ser ligeramente grave |
| `brightness`  | `+2.5` dB | Boost en altas frecuencias (≥3 kHz), añade presencia |
| `noise_scale` | `0.65`    | Más variación expresiva (default MeloTTS = 0.667) |
| `speed`       | `1.0`     | Velocidad natural |

Estos valores están fijados como defaults en `service.py` → `CASIOPY_DEFAULTS`.

## Checkpoint activo

```
logs/casiopy/G_24500.pth
logs/casiopy/config.json
```

## Cómo ajustar el pitch

Abre el Pitch Tester desde la UI del pipeline:
```
http://127.0.0.1:8820/static/pitch-test.html
```
o desde el botón **"Pitch Tester"** en el header del pipeline.
