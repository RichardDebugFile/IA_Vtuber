"""
Fix duplicate phrases in metadata.csv (Version 2)
- Uses dynamic phrase generation to ensure uniqueness
- Keep first occurrence of each phrase
- Generate guaranteed unique phrases for duplicates
- Delete associated .wav files
- Update generation_state.json to mark as pending
"""
import json
import random
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Templates for generating unique phrases
TEMPLATES = {
    "actions": [
        "Necesito {action} {object} porque {reason}",
        "Me gustaría {action} {object} para {reason}",
        "Debería {action} {object} antes de {reason}",
        "Tengo que {action} {object} porque {reason}",
        "Prefiero {action} {object} cuando {reason}",
        "Quiero {action} {object} porque {reason}",
        "Voy a {action} {object} para {reason}",
        "Puedo {action} {object} sin {reason}",
        "Debo {action} {object} durante {reason}",
        "Suelo {action} {object} después de {reason}",
    ],
    "observations": [
        "El {subject} {verb} {complement} de manera {adjective} y {adjective2}",
        "La {subject_fem} {verb} {complement} con {adjective} y mucha {emotion}",
        "Me fascina cómo el {subject} {verb} {complement} {adjective} cada día",
        "Es increíble que la {subject_fem} {verb} {complement} tan {adjective} siempre",
        "Observo que el {subject} {verb} {complement} de forma {adjective} constantemente",
        "Noto que la {subject_fem} {verb} {complement} {adjective} últimamente",
        "Descubro que el {subject} {verb} {complement} más {adjective} ahora",
        "Me sorprende que la {subject_fem} {verb} {complement} tan {adjective} hoy",
        "Veo que el {subject} {verb} {complement} {adjective} frecuentemente",
        "Compruebo que la {subject_fem} {verb} {complement} de modo {adjective} siempre",
    ],
    "questions": [
        "¿Has notado cómo {subject} {verb} {complement} últimamente de forma {adjective}?",
        "¿Te has preguntado por qué {subject} {verb} {complement} tan {adjective} ahora?",
        "¿Sabías que {subject} {verb} {complement} de manera {adjective} sorprendente?",
        "¿Recuerdas cuando {subject} {verb} {complement} más {adjective} que ahora?",
        "¿Has pensado en cómo {subject} {verb} {complement} {adjective} cada vez más?",
        "¿Te parece que {subject} {verb} {complement} demasiado {adjective} últimamente?",
        "¿Has observado que {subject} {verb} {complement} tan {adjective} recientemente?",
        "¿Podrías explicar por qué {subject} {verb} {complement} de forma {adjective}?",
        "¿Has considerado que {subject} {verb} {complement} más {adjective} ahora?",
        "¿Te diste cuenta de que {subject} {verb} {complement} tan {adjective} hoy?",
    ],
    "reflections": [
        "La {concept} es fundamental para {goal} y alcanzar {result} exitosamente",
        "El {concept_masc} nos ayuda a {goal} y conseguir {result} positivos",
        "Creo que la {concept} permite {goal} y obtener {result} mejores",
        "Pienso que el {concept_masc} facilita {goal} y lograr {result} óptimos",
        "Considero que la {concept} contribuye a {goal} y generar {result} valiosos",
        "Opino que el {concept_masc} apoya {goal} y crear {result} significativos",
        "Siento que la {concept} impulsa {goal} y desarrollar {result} importantes",
        "Encuentro que el {concept_masc} promueve {goal} y producir {result} efectivos",
        "Descubro que la {concept} fomenta {goal} y construir {result} duraderos",
        "Reconozco que el {concept_masc} estimula {goal} y establecer {result} sólidos",
    ],
}

WORD_BANKS = {
    "action": [
        "organizar", "preparar", "revisar", "actualizar", "mejorar",
        "terminar", "completar", "planificar", "estudiar", "practicar",
        "desarrollar", "implementar", "optimizar", "perfeccionar", "renovar",
        "transformar", "modificar", "ajustar", "configurar", "establecer",
        "diseñar", "crear", "construir", "elaborar", "formular",
        "investigar", "explorar", "descubrir", "analizar", "evaluar",
    ],
    "object": [
        "mi proyecto personal importante", "los documentos pendientes", "mi rutina diaria",
        "el sistema de organización", "mi espacio de trabajo", "las tareas acumuladas",
        "mi plan de acción", "los objetivos establecidos", "mi estrategia actual",
        "el cronograma detallado", "mi método de estudio", "los procesos internos",
        "mi técnica de trabajo", "el flujo de actividades", "mi enfoque profesional",
        "las prioridades definidas", "mi gestión del tiempo", "los recursos disponibles",
        "mi desarrollo personal", "las habilidades necesarias", "el conocimiento adquirido",
        "mi productividad diaria", "los hábitos establecidos", "el balance de vida",
    ],
    "reason": [
        "es fundamental para mi crecimiento", "mejorará mi eficiencia", "es necesario para avanzar",
        "aumentará mi productividad", "optimizará mis resultados", "fortalecerá mis capacidades",
        "ampliará mis oportunidades", "desarrollará nuevas competencias", "consolidará mi aprendizaje",
        "expandirá mis horizontes", "potenciará mis fortalezas", "impulsará mi progreso",
        "facilitará mi trabajo", "agilizará mis procesos", "simplificará las tareas",
        "reducirá los obstáculos", "eliminará las barreras", "superará los desafíos",
        "resolverá los problemas", "alcanzará las metas", "cumplirá los objetivos",
    ],
    "subject": [
        "sistema", "proceso", "método", "enfoque", "modelo",
        "proyecto", "plan", "programa", "esquema", "diseño",
        "mecanismo", "procedimiento", "algoritmo", "framework", "protocolo",
    ],
    "subject_fem": [
        "técnica", "estrategia", "metodología", "práctica", "dinámica",
        "estructura", "arquitectura", "configuración", "implementación", "aplicación",
        "solución", "propuesta", "iniciativa", "medida", "acción",
    ],
    "verb": [
        "funciona", "opera", "se desarrolla", "evoluciona", "progresa",
        "se transforma", "se adapta", "se optimiza", "se integra", "se coordina",
        "se sincroniza", "se ajusta", "se actualiza", "se mejora", "se perfecciona",
    ],
    "complement": [
        "con los objetivos planteados", "según las expectativas", "dentro de los parámetros",
        "conforme a los estándares", "de acuerdo con las normas", "siguiendo las directrices",
        "mediante los procedimientos", "a través de los procesos", "bajo las condiciones",
        "en los diferentes contextos", "con las herramientas disponibles", "usando los recursos",
    ],
    "adjective": [
        "eficiente", "efectiva", "óptima", "precisa", "consistente",
        "confiable", "estable", "flexible", "adaptable", "escalable",
        "robusta", "sólida", "integral", "completa", "exhaustiva",
        "detallada", "minuciosa", "rigurosa", "sistemática", "metódica",
        "estructurada", "organizada", "coherente", "lógica", "racional",
    ],
    "adjective2": [
        "productiva", "innovadora", "creativa", "práctica", "funcional",
        "útil", "valiosa", "significativa", "relevante", "importante",
        "fundamental", "esencial", "crucial", "crítica", "vital",
    ],
    "emotion": [
        "dedicación", "atención", "precisión", "exactitud", "claridad",
        "transparencia", "coherencia", "consistencia", "persistencia", "constancia",
    ],
    "concept": [
        "colaboración", "comunicación", "planificación", "organización", "coordinación",
        "innovación", "creatividad", "flexibilidad", "adaptabilidad", "resiliencia",
    ],
    "concept_masc": [
        "trabajo en equipo", "pensamiento crítico", "aprendizaje continuo", "desarrollo personal",
        "crecimiento profesional", "liderazgo efectivo", "compromiso diario", "esfuerzo constante",
    ],
    "goal": [
        "alcanzar nuestras metas", "cumplir objetivos", "superar desafíos", "resolver problemas",
        "desarrollar habilidades", "mejorar competencias", "fortalecer capacidades", "expandir conocimientos",
        "optimizar procesos", "maximizar resultados", "incrementar eficiencia", "potenciar rendimiento",
    ],
    "result": [
        "y resultados sostenibles", "con impacto duradero", "que generan valor",
        "de alto nivel", "excepcionales", "extraordinarios", "consistentes",
        "medibles y tangibles", "significativos y relevantes", "positivos y constructivos",
    ],
}

class UniquePhrasesGenerator:
    """Generator that ensures all phrases are unique."""

    def __init__(self):
        self.generated_phrases = set()
        self.existing_phrases = set()

    def add_existing_phrases(self, phrases):
        """Add existing phrases to avoid duplicates."""
        self.existing_phrases.update(phrases)
        self.generated_phrases.update(phrases)

    def generate_phrase(self):
        """Generate a unique phrase."""
        max_attempts = 1000

        for _ in range(max_attempts):
            # Randomly select a template category
            category = random.choice(list(TEMPLATES.keys()))
            template = random.choice(TEMPLATES[category])

            # Fill in the template with random words
            phrase = template
            for key in WORD_BANKS:
                if f"{{{key}}}" in phrase:
                    word = random.choice(WORD_BANKS[key])
                    phrase = phrase.replace(f"{{{key}}}", word)

            # Check if phrase is unique
            if phrase not in self.generated_phrases:
                self.generated_phrases.add(phrase)
                return phrase

        # If we couldn't generate a unique phrase, create one with a number
        base_phrase = "Esta es una frase única número {num} generada especialmente para este dataset de entrenamiento de voz"
        num = len(self.generated_phrases)
        phrase = base_phrase.format(num=num)
        self.generated_phrases.add(phrase)
        return phrase

def find_duplicates():
    """Find all duplicate phrases and identify which entries to keep/replace."""
    phrase_locations = defaultdict(list)

    # Read metadata.csv
    with open('metadata.csv', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        parts = line.strip().split('|')
        if len(parts) == 2:
            filename, phrase = parts
            phrase_locations[phrase].append((line_num, filename))

    # Find duplicates (keep first occurrence, mark others for replacement)
    entries_to_replace = []

    for phrase, locations in phrase_locations.items():
        if len(locations) > 1:
            # Keep first occurrence, replace the rest
            for line_num, filename in locations[1:]:
                entries_to_replace.append({
                    'line_num': line_num,
                    'filename': filename,
                    'old_phrase': phrase
                })

    return entries_to_replace, lines

def delete_audio_files(entries):
    """Delete .wav files for duplicate entries."""
    wavs_dir = Path('wavs')
    deleted_count = 0

    for entry in entries:
        audio_file = wavs_dir / f"{entry['filename']}.wav"
        if audio_file.exists():
            audio_file.unlink()
            deleted_count += 1
            if deleted_count <= 20:  # Only print first 20
                print(f"  Eliminado: {audio_file.name}")

    if deleted_count > 20:
        print(f"  ... y {deleted_count - 20} archivos más")

    return deleted_count

def update_metadata_csv(entries_to_replace, lines):
    """Update metadata.csv with new unique phrases."""
    # Initialize phrase generator
    generator = UniquePhrasesGenerator()

    # Add existing phrases (the ones we're keeping)
    existing_phrases = set()
    for line in lines:
        parts = line.strip().split('|')
        if len(parts) == 2:
            existing_phrases.add(parts[1])

    # Remove the duplicates we're replacing
    for entry in entries_to_replace:
        existing_phrases.discard(entry['old_phrase'])

    generator.add_existing_phrases(existing_phrases)

    # Update duplicate entries with unique phrases
    for i, entry in enumerate(entries_to_replace):
        line_idx = entry['line_num'] - 1  # Convert to 0-based index
        filename = entry['filename']

        # Generate unique phrase
        new_phrase = generator.generate_phrase()

        # Update line
        lines[line_idx] = f"{filename}|{new_phrase}\n"
        entry['new_phrase'] = new_phrase

        if i < 10:  # Print first 10
            print(f"  {filename}: nueva frase generada")

    if len(entries_to_replace) > 10:
        print(f"  ... y {len(entries_to_replace) - 10} frases más")

    # Write updated metadata
    with open('metadata.csv', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return entries_to_replace

def update_generation_state(entries_to_replace):
    """Update generation_state.json to mark entries as pending."""
    # Load state
    with open('generation_state.json', 'r', encoding='utf-8') as f:
        state = json.load(f)

    # Create a set of filenames to update
    filenames_to_update = {entry['filename'] for entry in entries_to_replace}

    # Update entries
    updated_count = 0
    for entry in state['entries']:
        if entry['filename'] in filenames_to_update:
            # Find the new phrase for this entry
            new_phrase = next((e['new_phrase'] for e in entries_to_replace
                             if e['filename'] == entry['filename']), None)

            if new_phrase:
                # Update counters
                if entry['status'] == 'completed':
                    state['completed'] -= 1
                elif entry['status'] == 'error':
                    state['failed'] -= 1

                # Reset entry to pending
                entry['status'] = 'pending'
                entry['text'] = new_phrase
                entry['duration_seconds'] = None
                entry['file_size_kb'] = None
                entry['generated_at'] = None
                entry['error_message'] = None
                entry['retry_count'] = 0

                updated_count += 1

    # Ensure status is idle
    state['status'] = 'idle'

    # Save updated state
    with open('generation_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return updated_count

def main():
    print("=" * 80)
    print("ELIMINANDO FRASES DUPLICADAS DEL DATASET (VERSION 2)")
    print("=" * 80)
    print()

    # Step 1: Find duplicates
    print("1. Identificando frases duplicadas...")
    entries_to_replace, lines = find_duplicates()
    print(f"   Encontradas {len(entries_to_replace)} entradas duplicadas para reemplazar")
    print()

    if len(entries_to_replace) == 0:
        print("No hay duplicados para eliminar!")
        return

    # Step 2: Delete audio files
    print("2. Eliminando archivos de audio duplicados...")
    deleted_count = delete_audio_files(entries_to_replace)
    print(f"   Total eliminados: {deleted_count} archivos .wav")
    print()

    # Step 3: Update metadata.csv
    print("3. Generando nuevas frases únicas y actualizando metadata.csv...")
    entries_to_replace = update_metadata_csv(entries_to_replace, lines)
    print(f"   Total actualizadas: {len(entries_to_replace)} frases en metadata.csv")
    print()

    # Step 4: Update generation_state.json
    print("4. Actualizando generation_state.json (marcando como pending)...")
    updated_count = update_generation_state(entries_to_replace)
    print(f"   Total actualizadas: {updated_count} entradas en el estado")
    print()

    print("=" * 80)
    print("PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 80)
    print()
    print(f"Resumen:")
    print(f"  - Frases duplicadas eliminadas: {len(entries_to_replace)}")
    print(f"  - Archivos .wav eliminados: {deleted_count}")
    print(f"  - Nuevas frases únicas generadas: {len(entries_to_replace)}")
    print(f"  - Entradas marcadas como 'pending': {updated_count}")
    print()
    print("Siguiente paso:")
    print("  1. Reinicia el servidor (start.bat)")
    print("  2. Haz clic en 'Sincronizar con archivos' en el dashboard")
    print("  3. Inicia la generación para crear los audios con las nuevas frases")
    print()
    print("Verificando que no queden duplicados...")

    # Verify no duplicates remain
    import subprocess
    result = subprocess.run(['python', 'find_duplicates.py'],
                          capture_output=True, text=True, encoding='utf-8')
    if "No se encontraron frases duplicadas" in result.stdout:
        print("✓ VERIFICADO: No quedan frases duplicadas en el dataset")
    else:
        first_line = result.stdout.split('\n')[0] if result.stdout else ""
        print(f"ADVERTENCIA: {first_line}")

if __name__ == "__main__":
    main()
