"""
Script de demostracion del nuevo sistema de batch mixto equilibrado.

Muestra como se procesan prioridades y regulares en cada batch.
"""


def simulate_batch_processing():
    """Simula el procesamiento de batches con la nueva logica."""

    # Configuracion
    BATCH_SIZE = 10
    MAX_PRIORITIES_PER_BATCH = 5

    # Escenarios de prueba
    scenarios = [
        {
            "name": "Escenario 1: Solo audios regulares",
            "priorities": 0,
            "regulars": 50
        },
        {
            "name": "Escenario 2: Pocos prioritarios (3) + muchos regulares (47)",
            "priorities": 3,
            "regulars": 47
        },
        {
            "name": "Escenario 3: Muchos prioritarios (20) + regulares (30)",
            "priorities": 20,
            "regulars": 30
        },
        {
            "name": "Escenario 4: Solo prioritarios (15)",
            "priorities": 15,
            "regulars": 0
        },
        {
            "name": "Escenario 5: Caso critico - usuario sigue marcando prioritarios",
            "priorities": 100,  # Usuario marca muchos para regenerar
            "regulars": 1900   # Muchos pendientes
        }
    ]

    for scenario in scenarios:
        print("\n" + "="*70)
        print(f"{scenario['name']}")
        print("="*70)
        print(f"Pendientes: {scenario['priorities']} prioritarios + {scenario['regulars']} regulares")
        print()

        priorities = scenario['priorities']
        regulars = scenario['regulars']
        batch_num = 1
        total_processed = 0

        while priorities > 0 or regulars > 0:
            # Calcular batch actual
            priority_in_batch = min(priorities, MAX_PRIORITIES_PER_BATCH)
            remaining_slots = BATCH_SIZE - priority_in_batch
            regular_in_batch = min(regulars, remaining_slots)

            total_in_batch = priority_in_batch + regular_in_batch

            # Mostrar batch
            priority_bar = "P" * priority_in_batch
            regular_bar = "R" * regular_in_batch
            batch_visual = f"[{priority_bar}{regular_bar}]"

            print(f"Batch {batch_num:2d}: {batch_visual:12s} = {priority_in_batch} prioritarios + {regular_in_batch} regulares = {total_in_batch} total")

            # Actualizar contadores
            priorities -= priority_in_batch
            regulars -= regular_in_batch
            total_processed += total_in_batch
            batch_num += 1

            # Limite de batches para evitar output muy largo
            if batch_num > 10:
                remaining_total = priorities + regulars
                print(f"... ({remaining_total} audios restantes serian procesados en {(remaining_total + BATCH_SIZE - 1) // BATCH_SIZE} batches mas)")
                break

        print(f"\nTotal procesado: {total_processed} audios en {batch_num - 1} batches")

        # Analisis del escenario
        if scenario['priorities'] > 0 and scenario['regulars'] > 0:
            print("\n[OK] ANALISIS: Prioritarios y regulares se procesan en PARALELO")
            print("  - Ningun tipo bloquea al otro")
            print("  - No hay 'vacios' en la generacion")

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("[OK] Los audios regulares SIEMPRE se procesan en cada batch")
    print("[OK] Los prioritarios toman maximo 5 slots, dejando 5 para regulares")
    print("[OK] Si hay menos de 5 prioritarios, los regulares llenan los slots")
    print("[OK] No hay bloqueo infinito ni 'vacios' en la generacion")
    print("="*70)


if __name__ == "__main__":
    print("\nDEMOSTRACION: Sistema de Batch Mixto Equilibrado")
    print("=" * 70)
    simulate_batch_processing()
