"""
Script de reparacion automatica de sincronizacion.

Corrige desincrornizaciones entre archivos en disco y generation_state.json.
"""

import json
import os
from pathlib import Path
from datetime import datetime


def fix_synchronization():
    """Fix synchronization between disk files and JSON state."""

    state_file = Path("generation_state.json")
    wavs_dir = Path("wavs")

    # Load state
    print("Cargando generation_state.json...")
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    # Get files on disk
    print("Escaneando archivos en disco...")
    actual_files = {f.stem: f for f in wavs_dir.glob('*.wav')}

    print(f"\nArchivos en disco: {len(actual_files)}")
    print(f"Completados en JSON: {state['completed']}")
    print()

    # Track changes
    files_fixed = []
    missing_fixed = []

    # Fix entries
    for entry in state['entries']:
        filename = entry['filename']
        audio_file = wavs_dir / f"{filename}.wav"

        # Case 1: File exists but status is not completed
        if audio_file.exists() and entry['status'] != 'completed':
            try:
                # Get file metadata (without reading audio content)
                file_size = audio_file.stat().st_size
                file_mtime = audio_file.stat().st_mtime

                # Update entry
                old_status = entry['status']
                entry['status'] = 'completed'
                # Set approximate duration based on file size (rough estimate)
                # Typical WAV: ~10KB/sec at 16kHz mono
                entry['duration_seconds'] = round((file_size / 1024) / 10.0, 2)
                entry['file_size_kb'] = file_size // 1024
                entry['generated_at'] = datetime.fromtimestamp(file_mtime).isoformat()
                entry['error_message'] = None

                # Update counters
                if old_status == 'error':
                    state['failed'] -= 1
                state['completed'] += 1

                files_fixed.append((entry['id'], filename, old_status))
                print(f"[FIX] ID {entry['id']} ({filename}): {old_status} -> completed")

            except Exception as e:
                print(f"[ERROR] No se pudo procesar {filename}: {e}")

        # Case 2: File doesn't exist but status is completed
        elif not audio_file.exists() and entry['status'] == 'completed':
            # Reset to pending
            entry['status'] = 'pending'
            entry['duration_seconds'] = None
            entry['file_size_kb'] = None
            entry['generated_at'] = None
            entry['error_message'] = None

            # Update counters
            state['completed'] -= 1

            missing_fixed.append((entry['id'], filename))
            print(f"[FIX] ID {entry['id']} ({filename}): completed -> pending (archivo no existe)")

    # Save updated state
    if files_fixed or missing_fixed:
        print(f"\nGuardando cambios a generation_state.json...")
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print("\n=== RESUMEN DE REPARACION ===")
        print(f"Archivos existentes sincronizados: {len(files_fixed)}")
        print(f"Archivos faltantes marcados como pendientes: {len(missing_fixed)}")
        print(f"Nuevo contador de completados: {state['completed']}")
        print(f"Total de archivos en disco: {len(actual_files)}")
        print("\n[OK] Sincronizacion reparada exitosamente!")
    else:
        print("\n[OK] No se encontraron problemas de sincronizacion.")

    return {
        "files_fixed": len(files_fixed),
        "missing_fixed": len(missing_fixed),
        "total_completed": state['completed'],
        "total_files": len(actual_files)
    }


if __name__ == "__main__":
    print("="*70)
    print("REPARACION AUTOMATICA DE SINCRONIZACION")
    print("="*70)
    print()

    result = fix_synchronization()

    print()
    print("="*70)
    print("PROCESO COMPLETADO")
    print("="*70)
