"""
Delete all completed audio files and mark them as pending.
This ensures all audios will be regenerated with the new unique texts.
"""
import json
from pathlib import Path

def delete_completed_audios():
    print("=" * 80)
    print("ELIMINANDO AUDIOS COMPLETADOS")
    print("=" * 80)
    print()

    # Load generation state
    print("1. Cargando generation_state.json...")
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)

    completed_entries = [e for e in state['entries'] if e['status'] == 'completed']
    print(f"   Encontradas {len(completed_entries)} entradas completadas")
    print()

    # Delete audio files
    wavs_dir = Path('wavs')
    deleted_count = 0

    print(f"2. Eliminando {len(completed_entries)} archivos .wav...")
    for i, entry in enumerate(completed_entries, 1):
        audio_file = wavs_dir / f"{entry['filename']}.wav"
        if audio_file.exists():
            audio_file.unlink()
            deleted_count += 1
            if deleted_count <= 20:
                print(f"   [{i}/{len(completed_entries)}] Eliminado: {entry['filename']}.wav")

        # Mark as pending
        entry['status'] = 'pending'
        entry['duration_seconds'] = None
        entry['file_size_kb'] = None
        entry['generated_at'] = None
        entry['error_message'] = None
        entry['retry_count'] = 0

        # Update progress every 100 entries
        if i % 100 == 0:
            print(f"   Progreso: {i}/{len(completed_entries)} procesados...")

    if deleted_count > 20:
        print(f"   ... y {deleted_count - 20} archivos más")

    print(f"\n   Total eliminados: {deleted_count} archivos")
    print()

    # Update state counters
    old_completed = state['completed']
    state['completed'] = 0
    state['failed'] = sum(1 for e in state['entries'] if e['status'] == 'error')
    state['status'] = 'idle'

    # Save updated state
    print("3. Guardando generation_state.json actualizado...")
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print("   [OK] Estado guardado")
    print()

    print("=" * 80)
    print("LIMPIEZA COMPLETADA EXITOSAMENTE")
    print("=" * 80)
    print()
    print(f"Resumen:")
    print(f"  - Archivos .wav eliminados: {deleted_count}")
    print(f"  - Entradas marcadas como 'pending': {len(completed_entries)}")
    print(f"  - Completados: {old_completed} -> 0")
    print(f"  - Pendientes ahora: {len([e for e in state['entries'] if e['status'] == 'pending'])}")
    print()
    print("Proximo paso:")
    print("  1. Recarga el dashboard con Ctrl+F5")
    print("  2. Haz clic en '🔄 Sincronizar con archivos'")
    print("  3. Inicia la generacion con '▶ Iniciar'")
    print()
    print("Todos los audios se regeneraran con los textos unicos actualizados.")
    print()

if __name__ == "__main__":
    try:
        delete_completed_audios()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
