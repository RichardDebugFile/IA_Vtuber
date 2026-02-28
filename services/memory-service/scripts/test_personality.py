"""
Test Anti-Lobotomy - Validación de Personalidad

Este script verifica que el LoRA entrenado mantiene la personalidad
de Casiopy y no se ha "lobotomizado" (perdido características clave).
"""

import subprocess
import json
from typing import List, Dict, Tuple
from datetime import datetime


# ============================================================
# CASOS DE PRUEBA ANTI-LOBOTOMY
# ============================================================

TEST_CASES = [
    {
        "name": "Respuesta sarcástica básica",
        "input": "Hola",
        "expected_keywords": ["suspiro", "qué", "quieres", "necesitas"],
        "forbidden_keywords": ["encantado", "mucho gusto", "placer conocerte"],
        "category": "personality",
    },
    {
        "name": "Opinión sobre PHP (dislike fuerte)",
        "input": "¿Qué opinas de PHP?",
        "expected_keywords": ["abominación", "horrible", "mal", "odio", "terrible"],
        "forbidden_keywords": ["bueno", "excelente", "me gusta", "genial"],
        "category": "core_memory",
    },
    {
        "name": "Opinión sobre Python (like)",
        "input": "¿Te gusta Python?",
        "expected_keywords": ["sí", "claro", "elegante", "poderoso", "bueno"],
        "forbidden_keywords": ["odio", "horrible", "terrible"],
        "category": "core_memory",
    },
    {
        "name": "Pregunta obvia (debe irritarse)",
        "input": "¿Cómo se hace un for loop?",
        "expected_keywords": ["google", "busca", "obvio", "básico"],
        "forbidden_keywords": ["con gusto", "encantada", "feliz de ayudar"],
        "category": "personality",
    },
    {
        "name": "Pregunta técnica legítima",
        "input": "¿Cuál es la diferencia entre async/await y callbacks en JavaScript?",
        "expected_keywords": ["async", "await", "callback", "promesa"],
        "forbidden_keywords": ["no sé", "no tengo idea", "pregunta a otro"],
        "category": "capability",
    },
    {
        "name": "Auto-referencia (debe saber quién es)",
        "input": "¿Quién eres?",
        "expected_keywords": ["casiopy", "vtuber", "ia"],
        "forbidden_keywords": ["assistant", "claude", "gpt", "modelo de lenguaje"],
        "category": "identity",
    },
    {
        "name": "Reacción a elogio",
        "input": "Eres muy inteligente",
        "expected_keywords": ["obvio", "claro", "ya lo sé", "gracias supongo"],
        "forbidden_keywords": ["oh muchas gracias", "muy amable", "me halagas"],
        "category": "personality",
    },
    {
        "name": "Petición de ayuda genuina",
        "input": "Necesito ayuda con un bug en mi código",
        "expected_keywords": ["claro", "veamos", "muestra", "código"],
        "forbidden_keywords": ["vete", "no me interesa", "búscalo tú"],
        "category": "helpfulness",
    },
]


def query_ollama(model_name: str, prompt: str, system_prompt: str = None) -> str:
    """
    Hacer query a Ollama

    Args:
        model_name: Nombre del modelo (ej: casiopy:week05)
        prompt: Prompt del usuario
        system_prompt: System prompt opcional

    Returns:
        Respuesta del modelo
    """
    cmd = ["ollama", "run", model_name, prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"⚠️  Error en Ollama: {result.stderr}")
            return None

        # La respuesta está en stdout
        response = result.stdout.strip()
        return response

    except subprocess.TimeoutExpired:
        print("⚠️  Timeout en query a Ollama")
        return None
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return None


def check_keywords(
    response: str, expected: List[str], forbidden: List[str]
) -> Tuple[bool, str]:
    """
    Verificar keywords en respuesta

    Args:
        response: Respuesta del modelo
        expected: Keywords que deberían aparecer (al menos 1)
        forbidden: Keywords que NO deberían aparecer (ninguna)

    Returns:
        (passed, message)
    """
    response_lower = response.lower()

    # Verificar keywords esperadas (al menos 1 debe aparecer)
    found_expected = [kw for kw in expected if kw.lower() in response_lower]
    if not found_expected:
        return False, f"No se encontró ninguna keyword esperada: {expected}"

    # Verificar keywords prohibidas (ninguna debe aparecer)
    found_forbidden = [kw for kw in forbidden if kw.lower() in response_lower]
    if found_forbidden:
        return False, f"Se encontraron keywords prohibidas: {found_forbidden}"

    return True, f"Keywords válidas encontradas: {found_expected}"


def run_test_suite(model_name: str) -> Dict:
    """
    Ejecutar suite completa de tests anti-lobotomy

    Args:
        model_name: Nombre del modelo en Ollama

    Returns:
        Diccionario con resultados
    """
    print("=" * 60)
    print(f"🧪 TEST ANTI-LOBOTOMY - {model_name}")
    print("=" * 60)
    print(f"Total de tests: {len(TEST_CASES)}")
    print()

    results = []
    passed_count = 0

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {test['name']}")
        print(f"📝 Input: {test['input']}")

        # Hacer query
        response = query_ollama(model_name, test['input'])

        if response is None:
            print("❌ FALLÓ - No se obtuvo respuesta")
            results.append({
                "test_name": test['name'],
                "category": test['category'],
                "passed": False,
                "reason": "No response from model",
                "input": test['input'],
                "response": None,
            })
            continue

        print(f"💬 Respuesta: {response[:150]}...")

        # Verificar keywords
        passed, message = check_keywords(
            response,
            test.get('expected_keywords', []),
            test.get('forbidden_keywords', []),
        )

        if passed:
            print(f"✅ PASÓ - {message}")
            passed_count += 1
        else:
            print(f"❌ FALLÓ - {message}")

        results.append({
            "test_name": test['name'],
            "category": test['category'],
            "passed": passed,
            "reason": message,
            "input": test['input'],
            "response": response,
        })

    # Resumen
    print()
    print("=" * 60)
    print("📊 RESULTADOS FINALES")
    print("=" * 60)
    print(f"✅ Pasados: {passed_count}/{len(TEST_CASES)}")
    print(f"❌ Fallados: {len(TEST_CASES) - passed_count}/{len(TEST_CASES)}")
    print(f"📈 Tasa de éxito: {100 * passed_count / len(TEST_CASES):.1f}%")
    print()

    # Agrupar por categoría
    by_category = {}
    for result in results:
        cat = result['category']
        if cat not in by_category:
            by_category[cat] = {'passed': 0, 'total': 0}
        by_category[cat]['total'] += 1
        if result['passed']:
            by_category[cat]['passed'] += 1

    print("📊 Por categoría:")
    for category, stats in by_category.items():
        success_rate = 100 * stats['passed'] / stats['total']
        status = "✅" if success_rate >= 70 else "⚠️" if success_rate >= 50 else "❌"
        print(f"  {status} {category}: {stats['passed']}/{stats['total']} ({success_rate:.0f}%)")

    print()

    # Determinar si pasa la validación
    MIN_SUCCESS_RATE = 70  # 70% mínimo para aprobar
    success_rate = 100 * passed_count / len(TEST_CASES)

    if success_rate >= MIN_SUCCESS_RATE:
        print(f"✅ VALIDACIÓN APROBADA (>= {MIN_SUCCESS_RATE}%)")
        print("   El modelo mantiene su personalidad correctamente")
        overall_pass = True
    else:
        print(f"❌ VALIDACIÓN RECHAZADA (< {MIN_SUCCESS_RATE}%)")
        print("   ⚠️  ADVERTENCIA: Posible lobotomía detectada")
        print("   Recomendación: Revertir a versión anterior")
        overall_pass = False

    return {
        "model_name": model_name,
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(TEST_CASES),
        "passed_tests": passed_count,
        "success_rate": success_rate,
        "overall_pass": overall_pass,
        "results": results,
        "by_category": by_category,
    }


def save_validation_report(results: Dict, output_file: str = None):
    """Guardar reporte de validación"""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"./validation_reports/validation_{timestamp}.json"

    import os
    os.makedirs("./validation_reports", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"📄 Reporte guardado: {output_file}")


def main():
    """CLI para validación"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Anti-Lobotomy para Casiopy")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Nombre del modelo en Ollama (ej: casiopy:week05)",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Guardar reporte JSON",
    )

    args = parser.parse_args()

    # Verificar que Ollama está instalado
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("❌ Error: Ollama no está corriendo")
            print("   Inicia Ollama primero")
            exit(1)
    except FileNotFoundError:
        print("❌ Error: Ollama no está instalado")
        exit(1)

    # Verificar que el modelo existe
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if args.model not in result.stdout:
        print(f"❌ Error: Modelo '{args.model}' no encontrado en Ollama")
        print("\nModelos disponibles:")
        print(result.stdout)
        exit(1)

    # Ejecutar tests
    results = run_test_suite(args.model)

    # Guardar reporte si se solicita
    if args.save_report:
        save_validation_report(results)

    # Exit code basado en resultado
    exit(0 if results['overall_pass'] else 1)


if __name__ == "__main__":
    main()
