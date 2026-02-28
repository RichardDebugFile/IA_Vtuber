"""Comprehensive dataset verification."""
from collections import Counter

def verify_dataset():
    phrases = []

    # Read metadata.csv
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split('|')
            if len(parts) == 2:
                filename, phrase = parts
                phrases.append(phrase)

    # Statistics
    total_phrases = len(phrases)
    unique_phrases = len(set(phrases))
    duplicates = total_phrases - unique_phrases

    # Word count analysis
    word_counts = [len(phrase.split()) for phrase in phrases]
    min_words = min(word_counts)
    max_words = max(word_counts)
    avg_words = sum(word_counts) / len(word_counts)

    # Character count analysis
    char_counts = [len(phrase) for phrase in phrases]
    min_chars = min(char_counts)
    max_chars = max(char_counts)
    avg_chars = sum(char_counts) / len(char_counts)

    # Find any phrases that are too short (< 9 words)
    short_phrases = [(i+1, phrase) for i, phrase in enumerate(phrases) if len(phrase.split()) < 9]

    # Find any phrases that are too long (> 20 words)
    long_phrases = [(i+1, phrase) for i, phrase in enumerate(phrases) if len(phrase.split()) > 20]

    print("=" * 80)
    print("VERIFICACION COMPLETA DEL DATASET")
    print("=" * 80)
    print()

    print("RESUMEN GENERAL:")
    print(f"  Total de frases: {total_phrases}")
    print(f"  Frases unicas: {unique_phrases}")
    print(f"  Duplicados: {duplicates}")
    print(f"  Porcentaje de unicidad: {(unique_phrases/total_phrases)*100:.2f}%")
    print()

    print("ANALISIS DE PALABRAS:")
    print(f"  Minimo de palabras: {min_words}")
    print(f"  Maximo de palabras: {max_words}")
    print(f"  Promedio de palabras: {avg_words:.1f}")
    print()

    print("ANALISIS DE CARACTERES:")
    print(f"  Minimo de caracteres: {min_chars}")
    print(f"  Maximo de caracteres: {max_chars}")
    print(f"  Promedio de caracteres: {avg_chars:.1f}")
    print()

    if short_phrases:
        print(f"ADVERTENCIA: {len(short_phrases)} frases con menos de 9 palabras:")
        for line_num, phrase in short_phrases[:5]:
            print(f"  Linea {line_num}: {phrase} ({len(phrase.split())} palabras)")
        if len(short_phrases) > 5:
            print(f"  ... y {len(short_phrases) - 5} mas")
        print()
    else:
        print("[OK] Todas las frases tienen al menos 9 palabras")
        print()

    if long_phrases:
        print(f"ADVERTENCIA: {len(long_phrases)} frases con mas de 20 palabras:")
        for line_num, phrase in long_phrases[:5]:
            print(f"  Linea {line_num}: {phrase} ({len(phrase.split())} palabras)")
        if len(long_phrases) > 5:
            print(f"  ... y {len(long_phrases) - 5} mas")
        print()
    else:
        print("[OK] Todas las frases tienen maximo 20 palabras")
        print()

    # Find duplicate counts if any
    if duplicates > 0:
        phrase_counts = Counter(phrases)
        duplicated_phrases = {phrase: count for phrase, count in phrase_counts.items() if count > 1}

        print(f"DUPLICADOS ENCONTRADOS ({len(duplicated_phrases)} frases):")
        for phrase, count in sorted(duplicated_phrases.items(), key=lambda x: -x[1])[:10]:
            print(f"  Aparece {count} veces: {phrase[:70]}...")
        print()
    else:
        print("[OK] No hay frases duplicadas")
        print()

    print("=" * 80)

    if duplicates == 0 and not short_phrases and not long_phrases:
        print("DATASET VERIFICADO CORRECTAMENTE")
        print("Todas las frases son unicas y tienen longitud adecuada (9-20 palabras)")
    else:
        print("SE ENCONTRARON PROBLEMAS EN EL DATASET")
        if duplicates > 0:
            print(f"  - {duplicates} frases duplicadas")
        if short_phrases:
            print(f"  - {len(short_phrases)} frases demasiado cortas")
        if long_phrases:
            print(f"  - {len(long_phrases)} frases demasiado largas")

    print("=" * 80)

if __name__ == "__main__":
    verify_dataset()
