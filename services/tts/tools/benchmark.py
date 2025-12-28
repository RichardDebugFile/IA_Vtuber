#!/usr/bin/env python
"""
Benchmark script for TTS Service.

This script performs comprehensive performance testing of the TTS service,
measuring various metrics across different scenarios.

Usage:
    python -m services.tts.src.benchmark
    python -m services.tts.src.benchmark --quick
    python -m services.tts.src.benchmark --emotions happy sad angry
    python -m services.tts.src.benchmark --output report.json
"""
import argparse
import asyncio
import base64
import json
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger


@dataclass
class BenchmarkResult:
    """Single benchmark result."""
    emotion: str
    text: str
    text_length: int
    success: bool
    duration_total: float  # Total time including network
    duration_generation: Optional[float] = None  # Only TTS generation (from metrics)
    audio_size: Optional[int] = None  # Size in bytes
    error: Optional[str] = None


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results."""
    total_requests: int
    successful: int
    failed: int
    success_rate: float
    avg_duration: float
    min_duration: float
    max_duration: float
    p50_duration: float
    p95_duration: float
    p99_duration: float
    avg_text_length: float
    avg_audio_size: float
    total_duration: float
    requests_per_second: float
    emotions_tested: List[str]
    timestamp: str


class TTSBenchmark:
    """TTS Service Benchmark."""

    def __init__(self, base_url: str = "http://127.0.0.1:8802"):
        self.base_url = base_url
        self.results: List[BenchmarkResult] = []

    async def check_service_health(self) -> bool:
        """Check if TTS service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/test/status",
                    timeout=10.0
                )
                data = response.json()

                if not data.get("ok"):
                    logger.error("TTS service not OK")
                    return False

                # Check Fish Audio backend
                backend = data.get("backends", {}).get("http", {})
                if not backend.get("healthy"):
                    logger.error("Fish Audio backend not healthy")
                    return False

                logger.info("✓ TTS service and Fish Audio are healthy")
                return True

        except Exception as e:
            logger.error(f"Failed to check service health: {e}")
            return False

    async def synthesize(
        self,
        text: str,
        emotion: str = "neutral"
    ) -> BenchmarkResult:
        """Synthesize speech and measure performance."""
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/synthesize",
                    json={"text": text, "emotion": emotion, "backend": "http"},
                    timeout=30.0
                )

                duration = time.perf_counter() - start_time

                if response.status_code != 200:
                    return BenchmarkResult(
                        emotion=emotion,
                        text=text,
                        text_length=len(text),
                        success=False,
                        duration_total=duration,
                        error=f"HTTP {response.status_code}"
                    )

                data = response.json()

                if not data.get("ok"):
                    return BenchmarkResult(
                        emotion=emotion,
                        text=text,
                        text_length=len(text),
                        success=False,
                        duration_total=duration,
                        error="Synthesis failed"
                    )

                # Calculate audio size
                audio_b64 = data.get("audio_b64", "")
                audio_size = len(base64.b64decode(audio_b64)) if audio_b64 else 0

                return BenchmarkResult(
                    emotion=emotion,
                    text=text,
                    text_length=len(text),
                    success=True,
                    duration_total=duration,
                    audio_size=audio_size
                )

        except Exception as e:
            duration = time.perf_counter() - start_time
            return BenchmarkResult(
                emotion=emotion,
                text=text,
                text_length=len(text),
                success=False,
                duration_total=duration,
                error=str(e)
            )

    async def run_benchmark(
        self,
        emotions: List[str],
        texts: Dict[str, str],
        iterations: int = 3
    ) -> List[BenchmarkResult]:
        """Run benchmark for multiple emotions and texts."""
        results = []

        total = len(emotions) * iterations
        current = 0

        logger.info(f"Running benchmark: {len(emotions)} emotions × {iterations} iterations = {total} requests")

        for emotion in emotions:
            text = texts.get(emotion, texts.get("neutral", "Test text"))

            for i in range(iterations):
                current += 1
                logger.info(f"[{current}/{total}] Testing {emotion} (iteration {i+1}/{iterations})")

                result = await self.synthesize(text, emotion)
                results.append(result)

                if result.success:
                    logger.success(
                        f"  ✓ {result.duration_total:.2f}s - {result.audio_size/1024:.1f}KB"
                    )
                else:
                    logger.error(f"  ✗ Failed: {result.error}")

                # Small delay between requests
                await asyncio.sleep(0.5)

        self.results.extend(results)
        return results

    def analyze_results(self) -> BenchmarkSummary:
        """Analyze benchmark results and generate summary."""
        if not self.results:
            raise ValueError("No results to analyze")

        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        durations = [r.duration_total for r in successful]
        text_lengths = [r.text_length for r in successful]
        audio_sizes = [r.audio_size for r in successful if r.audio_size]

        # Calculate percentiles
        sorted_durations = sorted(durations)
        p50_idx = int(len(sorted_durations) * 0.50)
        p95_idx = int(len(sorted_durations) * 0.95)
        p99_idx = int(len(sorted_durations) * 0.99)

        total_duration = sum(r.duration_total for r in self.results)

        emotions_tested = list(set(r.emotion for r in self.results))

        return BenchmarkSummary(
            total_requests=len(self.results),
            successful=len(successful),
            failed=len(failed),
            success_rate=len(successful) / len(self.results) * 100,
            avg_duration=statistics.mean(durations) if durations else 0,
            min_duration=min(durations) if durations else 0,
            max_duration=max(durations) if durations else 0,
            p50_duration=sorted_durations[p50_idx] if sorted_durations else 0,
            p95_duration=sorted_durations[p95_idx] if sorted_durations else 0,
            p99_duration=sorted_durations[p99_idx] if sorted_durations else 0,
            avg_text_length=statistics.mean(text_lengths) if text_lengths else 0,
            avg_audio_size=statistics.mean(audio_sizes) if audio_sizes else 0,
            total_duration=total_duration,
            requests_per_second=len(self.results) / total_duration if total_duration > 0 else 0,
            emotions_tested=sorted(emotions_tested),
            timestamp=datetime.now().isoformat()
        )

    def print_summary(self, summary: BenchmarkSummary):
        """Print benchmark summary to console."""
        print("\n" + "=" * 80)
        print("TTS BENCHMARK SUMMARY")
        print("=" * 80)
        print()

        print(f"Timestamp: {summary.timestamp}")
        print()

        print("REQUESTS")
        print(f"  Total:      {summary.total_requests}")
        print(f"  Successful: {summary.successful} ({summary.success_rate:.1f}%)")
        print(f"  Failed:     {summary.failed}")
        print()

        print("DURATION (seconds)")
        print(f"  Average:    {summary.avg_duration:.3f}s")
        print(f"  Min:        {summary.min_duration:.3f}s")
        print(f"  Max:        {summary.max_duration:.3f}s")
        print(f"  P50:        {summary.p50_duration:.3f}s")
        print(f"  P95:        {summary.p95_duration:.3f}s")
        print(f"  P99:        {summary.p99_duration:.3f}s")
        print()

        print("THROUGHPUT")
        print(f"  Total time:   {summary.total_duration:.2f}s")
        print(f"  Requests/sec: {summary.requests_per_second:.2f}")
        print()

        print("DATA")
        print(f"  Avg text length: {summary.avg_text_length:.0f} chars")
        print(f"  Avg audio size:  {summary.avg_audio_size/1024:.1f} KB")
        print()

        print("EMOTIONS TESTED")
        print(f"  {', '.join(summary.emotions_tested)}")
        print()

        # Performance assessment
        print("ASSESSMENT")
        if summary.avg_duration < 2.0:
            print("  [OK] Performance: EXCELLENT (< 2s average)")
        elif summary.avg_duration < 4.0:
            print("  [OK] Performance: GOOD (< 4s average)")
        elif summary.avg_duration < 6.0:
            print("  [!!] Performance: ACCEPTABLE (< 6s average)")
        else:
            print("  [XX] Performance: NEEDS IMPROVEMENT (> 6s average)")

        if summary.success_rate >= 99:
            print("  [OK] Reliability: EXCELLENT (99%+ success)")
        elif summary.success_rate >= 95:
            print("  [OK] Reliability: GOOD (95%+ success)")
        else:
            print("  [!!] Reliability: NEEDS IMPROVEMENT (< 95% success)")

        print()
        print("=" * 80)

    def save_results(self, output_path: Path):
        """Save detailed results to JSON file."""
        data = {
            "summary": asdict(self.analyze_results()),
            "results": [asdict(r) for r in self.results]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to: {output_path}")


# Predefined test texts for each emotion
DEFAULT_TEXTS = {
    "neutral": "Este es un texto de prueba con emoción neutral para el benchmark.",
    "happy": "¡Qué alegría! ¡Estoy muy feliz de realizar este benchmark!",
    "sad": "Me siento un poco triste al realizar estas pruebas...",
    "angry": "¡Esto es inaceptable! ¡Necesitamos mejores tiempos de respuesta!",
    "surprised": "¡Oh! ¡No puedo creer estos resultados del benchmark!",
    "excited": "¡Esto es increíble! ¡Estoy tan emocionada con estos números!",
    "confused": "Hmm... no estoy muy segura de qué significan estas métricas...",
    "upset": "Estoy algo disgustada con el rendimiento actual del sistema.",
    "fear": "¡Ten cuidado! ¡Estos tiempos de respuesta me dan miedo!",
    "asco": "Ugh, estos tiempos de carga son realmente desagradables.",
    "love": "Me encanta ver cómo mejora el rendimiento con cada optimización.",
    "bored": "Esto de ejecutar benchmarks es tan aburrido... suspiro.",
    "sleeping": "Mmm... estos benchmarks me dan tanto sueño... zzz.",
    "thinking": "Déjame pensar en cómo podemos optimizar estos tiempos cuidadosamente.",
}

# Extended texts for stress testing
EXTENDED_TEXTS = {
    "short": "Texto corto.",
    "medium": "Este es un texto de longitud media que contiene aproximadamente cincuenta caracteres para probar el rendimiento.",
    "long": "Este es un texto considerablemente más largo que sirve para evaluar el rendimiento del sistema de síntesis de voz cuando se enfrenta a textos extensos. Incluye múltiples oraciones, signos de puntuación variados, y permite medir cómo escala el tiempo de procesamiento con la longitud del texto. Es importante probar con diferentes longitudes para identificar posibles cuellos de botella.",
    "very_long": "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho tiempo que vivía un hidalgo de los de lanza en astillero, adarga antigua, rocín flaco y galgo corredor. Una olla de algo más vaca que carnero, salpicón las más noches, duelos y quebrantos los sábados, lantejas los viernes, algún palomino de añadidura los domingos, consumían las tres partes de su hacienda. El resto della concluían sayo de velarte, calzas de velludo para las fiestas, con sus pantuflos de lo mesmo, y los días de entresemana se honraba con su vellorí de lo más fino."
}


async def main():
    """Main benchmark execution."""
    parser = argparse.ArgumentParser(description="TTS Service Benchmark")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8802",
        help="TTS service URL (default: http://127.0.0.1:8802)"
    )
    parser.add_argument(
        "--emotions",
        nargs="+",
        help="Emotions to test (default: neutral happy sad angry)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Iterations per emotion (default: 3)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test (1 iteration, 3 emotions)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full test (all 14 emotions, 5 iterations)"
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help="Stress test (multiple text lengths)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for results"
    )

    args = parser.parse_args()

    # Configure test parameters
    if args.quick:
        emotions = ["neutral", "happy", "sad"]
        iterations = 1
        logger.info("Running QUICK benchmark")
    elif args.full:
        emotions = list(DEFAULT_TEXTS.keys())
        iterations = 5
        logger.info("Running FULL benchmark")
    elif args.stress:
        emotions = ["neutral"]
        iterations = 3
        logger.info("Running STRESS benchmark (multiple text lengths)")
    else:
        emotions = args.emotions or ["neutral", "happy", "sad", "angry"]
        iterations = args.iterations
        logger.info("Running CUSTOM benchmark")

    # Initialize benchmark
    benchmark = TTSBenchmark(args.url)

    # Check service health
    logger.info("Checking TTS service health...")
    if not await benchmark.check_service_health():
        logger.error("Service is not healthy. Aborting benchmark.")
        return 1

    print()

    # Run benchmark
    if args.stress:
        # Test different text lengths
        for length_type, text in EXTENDED_TEXTS.items():
            logger.info(f"\nTesting {length_type} text ({len(text)} chars)")
            await benchmark.run_benchmark(
                emotions=["neutral"],
                texts={"neutral": text},
                iterations=iterations
            )
    else:
        # Normal benchmark
        await benchmark.run_benchmark(
            emotions=emotions,
            texts=DEFAULT_TEXTS,
            iterations=iterations
        )

    # Analyze and display results
    summary = benchmark.analyze_results()
    benchmark.print_summary(summary)

    # Save results if requested
    if args.output:
        benchmark.save_results(args.output)
    else:
        # Default output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = Path(f"benchmark_results_{timestamp}.json")
        benchmark.save_results(default_output)

    # Return exit code based on success rate
    if summary.success_rate < 95:
        logger.warning("Success rate below 95%")
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
