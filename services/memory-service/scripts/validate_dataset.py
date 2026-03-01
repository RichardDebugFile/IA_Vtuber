"""
Dataset Validator - Casiopy Personality
Valida estructura y estadísticas del dataset de entrenamiento
"""

import json
from pathlib import Path
from collections import Counter


def validate_dataset(dataset_path: str):
    """
    Valida dataset en formato ChatML

    Args:
        dataset_path: Path al archivo .jsonl
    """

    print(f"[*] Validando dataset: {dataset_path}")
    print()

    # Cargar dataset
    dataset = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
                dataset.append(entry)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Error en linea {i}: {e}")
                return False

    print(f"[OK] Dataset cargado: {len(dataset)} ejemplos")
    print()

    # Validar estructura
    print("[*] Validando estructura ChatML...")
    errors = []

    for i, entry in enumerate(dataset, 1):
        # Validar que tenga 'messages'
        if 'messages' not in entry:
            errors.append(f"Entrada {i}: Falta campo 'messages'")
            continue

        messages = entry['messages']

        # Validar 3 mensajes (system, user, assistant)
        if len(messages) != 3:
            errors.append(f"Entrada {i}: Esperados 3 mensajes, encontrados {len(messages)}")
            continue

        # Validar roles
        expected_roles = ['system', 'user', 'assistant']
        actual_roles = [msg.get('role') for msg in messages]

        if actual_roles != expected_roles:
            errors.append(f"Entrada {i}: Roles incorrectos. Esperados {expected_roles}, encontrados {actual_roles}")
            continue

        # Validar que cada mensaje tenga contenido
        for j, msg in enumerate(messages):
            if 'content' not in msg or not msg['content'].strip():
                errors.append(f"Entrada {i}, Mensaje {j}: Contenido vacío")

    if errors:
        print("[ERROR] Errores de estructura encontrados:")
        for error in errors[:10]:  # Mostrar solo primeros 10
            print(f"   - {error}")
        if len(errors) > 10:
            print(f"   ... y {len(errors) - 10} errores más")
        return False

    print("[OK] Estructura ChatML valida")
    print()

    # Estadísticas
    print("[*] Estadísticas del dataset:")
    print()

    # Longitud de respuestas
    response_lengths = []
    for entry in dataset:
        response = entry['messages'][2]['content']
        word_count = len(response.split())
        response_lengths.append(word_count)

    avg_length = sum(response_lengths) / len(response_lengths)
    min_length = min(response_lengths)
    max_length = max(response_lengths)

    print(f"[STATS] Longitud de respuestas:")
    print(f"   - Promedio: {avg_length:.1f} palabras")
    print(f"   - Minimo: {min_length} palabras")
    print(f"   - Maximo: {max_length} palabras")
    print()

    # Distribución de longitudes
    length_ranges = {
        "Muy cortas (1-10)": sum(1 for l in response_lengths if 1 <= l <= 10),
        "Cortas (11-20)": sum(1 for l in response_lengths if 11 <= l <= 20),
        "Medianas (21-40)": sum(1 for l in response_lengths if 21 <= l <= 40),
        "Largas (41-60)": sum(1 for l in response_lengths if 41 <= l <= 60),
        "Muy largas (61+)": sum(1 for l in response_lengths if l > 60),
    }

    print(f"[STATS] Distribucion de longitudes:")
    for range_name, count in length_ranges.items():
        percentage = (count / len(dataset)) * 100
        print(f"   - {range_name}: {count} ({percentage:.1f}%)")
    print()

    # Palabras más comunes en preguntas
    user_inputs = [entry['messages'][1]['content'] for entry in dataset]
    all_words = ' '.join(user_inputs).lower().split()
    most_common = Counter(all_words).most_common(10)

    print(f"[STATS] Palabras mas comunes en preguntas:")
    for word, count in most_common:
        print(f"   - '{word}': {count} veces")
    print()

    # Buscar profanidad
    profanity_words = ['mierda', 'carajo', 'hijo de puta', 'puta', 'pendejo', 'imbecil', 'idiota', 'fuck']
    profanity_count = 0

    for entry in dataset:
        response = entry['messages'][2]['content'].lower()
        if any(word in response for word in profanity_words):
            profanity_count += 1

    print(f"[STATS] Respuestas con profanidad: {profanity_count} ({(profanity_count/len(dataset)*100):.1f}%)")
    print()

    # Tamaño del archivo
    file_size = Path(dataset_path).stat().st_size / (1024 * 1024)  # MB
    print(f"[STATS] Tamano del archivo: {file_size:.2f} MB")
    print()

    print("[OK] Validacion completada exitosamente")
    print()

    return True


def validate_dataset_flexible(dataset_path: str, min_count: int = 50) -> dict:
    """
    Valida un dataset episódico en formato ChatML, aceptando tanto
    el formato completo (system+user+assistant) como el episódico (user+assistant).

    Args:
        dataset_path: Path al archivo .jsonl
        min_count: Mínimo de ejemplos requeridos (default 50)

    Returns:
        Dict con: status ("success"|"failed"), count, reason, errors
    """
    path = Path(dataset_path)
    if not path.exists():
        return {"status": "failed", "count": 0, "reason": "archivo no encontrado", "errors": []}

    dataset = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    dataset.append(json.loads(line))
                except json.JSONDecodeError as e:
                    return {
                        "status": "failed",
                        "count": 0,
                        "reason": f"JSON inválido en línea {i}: {e}",
                        "errors": [],
                    }
    except Exception as e:
        return {"status": "failed", "count": 0, "reason": str(e), "errors": []}

    if not dataset:
        return {"status": "failed", "count": 0, "reason": "archivo vacío", "errors": []}

    valid_sequences = [
        ["system", "user", "assistant"],
        ["user", "assistant"],
    ]
    errors = []
    for i, entry in enumerate(dataset, 1):
        if "messages" not in entry:
            errors.append(f"Entrada {i}: falta 'messages'")
            continue
        roles = [m.get("role") for m in entry["messages"]]
        if roles not in valid_sequences:
            errors.append(f"Entrada {i}: roles inválidos {roles}")
            continue
        for j, msg in enumerate(entry["messages"]):
            if not msg.get("content", "").strip():
                errors.append(f"Entrada {i}, mensaje {j}: contenido vacío")

    if errors:
        return {
            "status": "failed",
            "count": len(dataset),
            "reason": f"{len(errors)} error(es) de estructura",
            "errors": errors[:10],
        }

    if len(dataset) < min_count:
        return {
            "status": "failed",
            "count": len(dataset),
            "reason": f"ejemplos insuficientes: {len(dataset)} < {min_count} mínimo requerido",
            "errors": [],
        }

    return {"status": "success", "count": len(dataset), "reason": None, "errors": []}


if __name__ == "__main__":
    import sys

    # Buscar dataset v1 por defecto
    default_path = Path(__file__).parent.parent / "exports" / "personality" / "v1_production" / "casiopy_personality_v1.0.0.jsonl"

    dataset_path = sys.argv[1] if len(sys.argv) > 1 else str(default_path)

    if not Path(dataset_path).exists():
        print(f"[ERROR] Archivo no encontrado: {dataset_path}")
        sys.exit(1)

    success = validate_dataset(dataset_path)
    sys.exit(0 if success else 1)
