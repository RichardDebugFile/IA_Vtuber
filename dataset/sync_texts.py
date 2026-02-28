"""
Synchronize texts from metadata.csv to generation_state.json.
This fixes the issue where generation_state.json has old duplicate texts
while metadata.csv has been corrected with unique phrases.
"""
import json

def sync_texts():
    print("=" * 80)
    print("SINCRONIZANDO TEXTOS: metadata.csv -> generation_state.json")
    print("=" * 80)
    print()

    # Step 1: Read texts from metadata.csv
    print("1. Leyendo textos desde metadata.csv...")
    metadata_texts = {}
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) == 2:
                filename, text = parts
                # Extract ID from filename (e.g., casiopy_0073 -> 73)
                entry_id = int(filename.split('_')[1])
                metadata_texts[entry_id] = text

    print(f"   Leídos {len(metadata_texts)} textos desde metadata.csv")
    print()

    # Step 2: Load generation_state.json
    print("2. Cargando generation_state.json...")
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)

    print(f"   Cargadas {len(state['entries'])} entradas")
    print()

    # Step 3: Check for duplicates in current state
    from collections import Counter
    current_texts = [e['text'] for e in state['entries']]
    text_counts = Counter(current_texts)
    duplicates = {text: count for text, count in text_counts.items() if count > 1}

    print(f"3. Estado actual del generation_state.json:")
    print(f"   Duplicados encontrados: {len(duplicates)} frases")
    if duplicates:
        print(f"   Ejemplos de duplicados:")
        for text, count in list(duplicates.items())[:5]:
            print(f"     {count}x: {text[:70]}...")
    print()

    # Step 4: Synchronize texts
    print("4. Sincronizando textos...")
    updated_count = 0
    mismatches = []

    for entry in state['entries']:
        entry_id = entry['id']
        old_text = entry['text']

        if entry_id in metadata_texts:
            new_text = metadata_texts[entry_id]

            if old_text != new_text:
                entry['text'] = new_text
                updated_count += 1
                mismatches.append({
                    'id': entry_id,
                    'filename': entry['filename'],
                    'old': old_text[:60],
                    'new': new_text[:60]
                })
        else:
            print(f"   ADVERTENCIA: ID {entry_id} no encontrado en metadata.csv")

    print(f"   Actualizadas {updated_count} entradas")
    print()

    # Show some examples of changes
    if mismatches:
        print("   Ejemplos de cambios (primeros 5):")
        for mismatch in mismatches[:5]:
            print(f"     ID {mismatch['id']} ({mismatch['filename']}):")
            print(f"       Antes: {mismatch['old']}...")
            print(f"       Ahora: {mismatch['new']}...")
        print()

    # Step 5: Verify no duplicates remain
    print("5. Verificando que no queden duplicados...")
    new_texts = [e['text'] for e in state['entries']]
    new_text_counts = Counter(new_texts)
    new_duplicates = {text: count for text, count in new_text_counts.items() if count > 1}

    if new_duplicates:
        print(f"   ERROR: Aún hay {len(new_duplicates)} frases duplicadas:")
        for text, count in list(new_duplicates.items())[:5]:
            print(f"     {count}x: {text[:70]}...")
        print()
        print("   Esto indica que metadata.csv también tiene duplicados.")
        return False
    else:
        print("   [OK] No quedan duplicados en generation_state.json")
        print()

    # Step 6: Save updated state
    print("6. Guardando generation_state.json actualizado...")
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print("   [OK] Archivo guardado")
    print()

    print("=" * 80)
    print("SINCRONIZACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 80)
    print()
    print(f"Resumen:")
    print(f"  - Entradas totales: {len(state['entries'])}")
    print(f"  - Textos actualizados: {updated_count}")
    print(f"  - Duplicados eliminados: {len(duplicates)} -> 0")
    print()
    print("IMPORTANTE:")
    print("  Los audios ya generados con textos duplicados permanecen en el disco.")
    print("  Para regenerarlos con los nuevos textos:")
    print("    1. Ve al dashboard")
    print("    2. Usa el botón 'Sincronizar con archivos' para detectar cambios")
    print("    3. Usa 'Regenerar' en los audios que necesites actualizar")
    print()

    return True

if __name__ == "__main__":
    sync_texts()
