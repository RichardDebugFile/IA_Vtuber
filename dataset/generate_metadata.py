"""Generate metadata.csv with 2000 dataset entries."""

import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.content_generator import ContentGenerator


def main():
    """Generate and save metadata.csv."""
    print("Generando dataset de 2000 clips...")

    # Generate dataset
    dataset = ContentGenerator.generate_dataset(2000)

    # Get statistics
    stats = ContentGenerator.get_text_stats(dataset)

    # Save to pipe-separated format (filename|text) without headers
    csv_file = Path("metadata.csv")
    with open(csv_file, 'w', encoding='utf-8') as f:
        for entry in dataset:
            # Format: filename|text (no .wav extension in filename)
            f.write(f"{entry['filename']}|{entry['text']}\n")

    print(f"\n[OK] Generados {len(dataset)} clips en {csv_file}")
    print("\nEstadisticas del dataset:")
    print(f"  Total de entradas:  {stats['total_entries']}")
    print(f"  Textos unicos:      {stats['unique_texts']}")
    print(f"  Duplicados:         {stats['duplicates']}")
    print(f"  Longitud promedio:  {stats['avg_text_length_chars']} caracteres")
    print(f"  Palabras promedio:  {stats['avg_word_count']} palabras")
    print(f"  Longitud minima:    {stats['min_length']} caracteres ({stats['min_words']} palabras)")
    print(f"  Longitud maxima:    {stats['max_length']} caracteres ({stats['max_words']} palabras)")

    print(f"\nFormato: filename|text (sin encabezados, sin columna de emocion)")
    print("El modelo aprendera prosodia directamente del audio")
    print("\nAhora ejecuta start.bat para iniciar el generador de dataset")


if __name__ == "__main__":
    main()
