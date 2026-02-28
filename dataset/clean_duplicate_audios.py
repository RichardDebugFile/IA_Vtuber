"""
Clean audio files that were generated with duplicate texts.
This script:
1. Compares current texts in generation_state.json with metadata.csv
2. Identifies entries that were updated (had duplicate texts)
3. Deletes their .wav files
4. Marks them as 'pending' for regeneration
"""
import json
from pathlib import Path
from collections import defaultdict

def identify_entries_to_clean():
    """
    Identify entries that need to be cleaned by comparing
    which texts appear multiple times in already-generated audios.
    """
    print("=" * 80)
    print("LIMPIANDO AUDIOS GENERADOS CON TEXTOS DUPLICADOS")
    print("=" * 80)
    print()

    # Load generation state
    print("1. Cargando generation_state.json...")
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f"   Cargadas {len(state['entries'])} entradas")
    print()

    # Group completed entries by text (to find which were generated with same text)
    print("2. Buscando audios que fueron generados con textos que ahora están actualizados...")

    # Since we already synced, we need a different approach:
    # Mark as pending all entries that are 'completed' but were updated by sync_texts.py
    # We can identify these by checking which entries have generated_at timestamps
    # that are older than the metadata.csv modification time

    metadata_path = Path('metadata.csv')
    metadata_mtime = metadata_path.stat().st_mtime if metadata_path.exists() else 0

    # Read metadata.csv to get current texts
    metadata_texts = {}
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) == 2:
                filename, text = parts
                entry_id = int(filename.split('_')[1])
                metadata_texts[entry_id] = text

    # Strategy: Since we can't know which were duplicates without history,
    # we'll identify entries that are 'completed' but their .wav files
    # should be regenerated because the text was updated.
    # The safest approach is to look at the generation log or compare with metadata.

    # Alternative strategy: Mark all 'completed' entries that don't have
    # matching text in their audio (we can't check this without listening)

    # Best strategy: Ask user to confirm deletion of specific ranges or all

    # For now, let's take a conservative approach:
    # - Delete only files that are confirmed duplicates
    # - Or delete all and regenerate (safest but takes time)

    print("   NOTA: No podemos identificar automáticamente cuáles audios tienen")
    print("   textos duplicados sin comparar archivos o mantener historial.")
    print()

    # Show statistics
    completed = [e for e in state['entries'] if e['status'] == 'completed']
    pending = [e for e in state['entries'] if e['status'] == 'pending']
    failed = [e for e in state['entries'] if e['status'] == 'error']

    print("Estado actual:")
    print(f"  - Completados: {len(completed)}")
    print(f"  - Pendientes: {len(pending)}")
    print(f"  - Fallidos: {len(failed)}")
    print()

    # Ask user what to do
    print("Opciones disponibles:")
    print("  1. Eliminar TODOS los audios completados y regenerar desde cero (más seguro)")
    print("  2. Mantener audios y solo regenerar los pendientes (actual)")
    print("  3. Cancelar")
    print()

    choice = input("Selecciona una opción (1/2/3): ").strip()

    if choice == '1':
        return delete_all_and_reset(state, completed)
    elif choice == '2':
        print("\nNo se eliminarán audios. Puedes iniciar la generación de pendientes.")
        return 0
    else:
        print("\nOperación cancelada.")
        return 0

def delete_all_and_reset(state, completed_entries):
    """Delete all completed audio files and mark as pending."""
    print()
    print("=" * 80)
    print("ELIMINANDO TODOS LOS AUDIOS COMPLETADOS")
    print("=" * 80)
    print()

    confirm = input(f"¿Estás seguro de eliminar {len(completed_entries)} audios? (si/no): ").strip().lower()

    if confirm != 'si':
        print("Operación cancelada.")
        return 0

    wavs_dir = Path('wavs')
    deleted_count = 0

    print(f"\nEliminando {len(completed_entries)} archivos .wav...")
    for i, entry in enumerate(completed_entries, 1):
        audio_file = wavs_dir / f"{entry['filename']}.wav"
        if audio_file.exists():
            audio_file.unlink()
            deleted_count += 1
            if deleted_count <= 10:
                print(f"  [{i}/{len(completed_entries)}] Eliminado: {entry['filename']}.wav")

        # Mark as pending
        entry['status'] = 'pending'
        entry['duration_seconds'] = None
        entry['file_size_kb'] = None
        entry['generated_at'] = None
        entry['error_message'] = None
        entry['retry_count'] = 0

        # Update progress every 100 entries
        if i % 100 == 0:
            print(f"  Progreso: {i}/{len(completed_entries)} procesados...")

    if deleted_count > 10:
        print(f"  ... y {deleted_count - 10} archivos más")

    print(f"\nTotal eliminados: {deleted_count} archivos")
    print()

    # Update state counters
    state['completed'] = 0
    state['failed'] = sum(1 for e in state['entries'] if e['status'] == 'error')
    state['status'] = 'idle'

    # Save updated state
    print("Guardando generation_state.json actualizado...")
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print("[OK] Estado guardado")
    print()

    print("=" * 80)
    print("LIMPIEZA COMPLETADA")
    print("=" * 80)
    print()
    print(f"Resumen:")
    print(f"  - Archivos eliminados: {deleted_count}")
    print(f"  - Entradas marcadas como 'pending': {len(completed_entries)}")
    print(f"  - Total pendientes ahora: {len([e for e in state['entries'] if e['status'] == 'pending'])}")
    print()
    print("Siguiente paso:")
    print("  1. Recarga el dashboard (Ctrl+F5)")
    print("  2. Haz clic en 'Sincronizar con archivos'")
    print("  3. Inicia la generación con '▶ Iniciar'")
    print()

    return deleted_count

def main():
    try:
        identify_entries_to_clean()
    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
