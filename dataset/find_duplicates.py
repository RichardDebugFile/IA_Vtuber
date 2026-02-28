"""Find duplicate phrases in metadata.csv"""
import csv
from collections import defaultdict

def find_duplicates():
    # Dictionary to track phrases and their line numbers
    phrase_locations = defaultdict(list)

    # Read metadata.csv
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split('|')
            if len(parts) == 2:
                filename, phrase = parts
                phrase_locations[phrase].append((line_num, filename))

    # Find duplicates (phrases that appear more than once)
    duplicates = {phrase: locations for phrase, locations in phrase_locations.items()
                  if len(locations) > 1}

    if not duplicates:
        print("No se encontraron frases duplicadas")
        return

    print(f"\n=== FRASES DUPLICADAS ENCONTRADAS: {len(duplicates)} ===\n")

    for phrase, locations in sorted(duplicates.items()):
        print(f"Frase: \"{phrase}\"")
        print(f"Aparece {len(locations)} veces en:")
        for line_num, filename in locations:
            print(f"  - Linea {line_num}: {filename}")
        print()

if __name__ == "__main__":
    find_duplicates()
