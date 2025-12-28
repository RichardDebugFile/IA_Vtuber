"""
Conversation TTS Engine - Optimizado para baja latencia en conversaciones en tiempo real

Este módulo implementa un sistema de síntesis de voz optimizado para conversaciones,
con las siguientes características:
- Streaming por oraciones (Time To First Audio < 5s)
- Procesamiento paralelo de chunks
- Predicción de tiempos de generación
- Caché de frases comunes
"""
import asyncio
import re
import time
from dataclasses import dataclass
from typing import List, AsyncGenerator, Optional, Dict
from collections import deque
from loguru import logger


@dataclass
class SentenceChunk:
    """Representa un fragmento de texto (oración) para procesar."""
    text: str
    emotion: str
    index: int
    estimated_duration_ms: float = 0.0


@dataclass
class AudioChunk:
    """Representa un chunk de audio generado."""
    audio_bytes: bytes
    sentence_index: int
    duration_ms: float
    text: str
    emotion: str


class SentenceSplitter:
    """Divide texto en oraciones de forma inteligente para procesamiento."""

    # Patrones para detectar fin de oración
    SENTENCE_ENDINGS = re.compile(r'([.!?]+[\s\n]+|[.!?]+$)')

    # Separadores adicionales (comas, punto y coma) para chunks muy largos
    SOFT_BREAKS = re.compile(r'([,;][\s]+)')

    # Longitud máxima de chunk (por límites de VRAM)
    MAX_CHUNK_LENGTH = 100

    # Configuración para modo streamer
    MIN_WORDS_PER_CHUNK = 3  # Mínimo de palabras por chunk
    TARGET_WORDS_PER_CHUNK = 6  # Objetivo óptimo para balancear generación/reproducción

    @staticmethod
    def count_words(text: str) -> int:
        """Cuenta palabras en un texto."""
        return len(text.strip().split())

    @staticmethod
    def split_for_streaming(text: str, max_words: int = 10) -> List[str]:
        """
        Divide texto por comas con fusión inteligente para streaming.

        Estrategia:
        1. Dividir por comas
        2. Contar palabras en cada segmento
        3. Fusionar segmentos pequeños para optimizar batch size
        4. Mantener balance entre tiempo de generación y reproducción

        Args:
            text: Texto completo a dividir
            max_words: Máximo de palabras por chunk (para controlar tiempo de generación)

        Returns:
            Lista de segmentos optimizados para streaming

        Example:
            "Hola, me llamo Casiopy, mucho gusto mi gente!"
            → ["Hola, me llamo Casiopy,", "mucho gusto mi gente!"]
        """
        text = text.strip()
        if not text:
            return []

        # Dividir por comas, manteniendo las comas en los segmentos
        parts = re.split(r'(,)', text)

        # Reconstruir segmentos con sus comas
        raw_segments = []
        current = ""
        for part in parts:
            current += part
            if part == ",":
                raw_segments.append(current.strip())
                current = ""

        # Agregar último segmento si existe (sin coma final)
        if current.strip():
            raw_segments.append(current.strip())

        # Si solo hay un segmento, retornarlo directamente
        if len(raw_segments) <= 1:
            return raw_segments

        # Fusionar segmentos pequeños
        merged = []
        buffer = ""
        buffer_words = 0

        for segment in raw_segments:
            segment_words = SentenceSplitter.count_words(segment)

            # Si el buffer está vacío, agregar este segmento
            if not buffer:
                buffer = segment
                buffer_words = segment_words
                continue

            # Calcular palabras totales si fusionamos
            total_words = buffer_words + segment_words

            # Decidir si fusionar o separar
            if total_words <= max_words:
                # Fusionar si no excede el máximo
                buffer = buffer + " " + segment
                buffer_words = total_words
            else:
                # Si el buffer actual es muy pequeño pero fusionar excede el máximo,
                # verificar qué es mejor
                if buffer_words < SentenceSplitter.MIN_WORDS_PER_CHUNK:
                    # Fusionar de todos modos para evitar chunks muy pequeños
                    buffer = buffer + " " + segment
                    buffer_words = total_words
                else:
                    # Guardar buffer actual y empezar nuevo
                    merged.append(buffer)
                    buffer = segment
                    buffer_words = segment_words

        # Agregar último buffer
        if buffer:
            merged.append(buffer)

        return merged

    @staticmethod
    def split(text: str) -> List[str]:
        """
        Divide texto en oraciones manteniendo puntuación y contexto.

        Args:
            text: Texto completo a dividir

        Returns:
            Lista de oraciones
        """
        # Limpieza inicial
        text = text.strip()
        if not text:
            return []

        # Dividir por oraciones completas
        sentences = []
        parts = SentenceSplitter.SENTENCE_ENDINGS.split(text)

        current = ""
        for i, part in enumerate(parts):
            if not part.strip():
                continue

            # Si es un separador, agregarlo a la oración anterior
            if SentenceSplitter.SENTENCE_ENDINGS.match(part):
                current += part
                if current.strip():
                    sentences.append(current.strip())
                    current = ""
            else:
                current += part

        # Agregar última oración si existe
        if current.strip():
            sentences.append(current.strip())

        # Dividir oraciones muy largas por comas/punto y coma
        final_sentences = []
        for sentence in sentences:
            if len(sentence) <= SentenceSplitter.MAX_CHUNK_LENGTH:
                final_sentences.append(sentence)
            else:
                # Dividir por comas
                sub_parts = SentenceSplitter.SOFT_BREAKS.split(sentence)
                current_chunk = ""

                for part in sub_parts:
                    if len(current_chunk + part) <= SentenceSplitter.MAX_CHUNK_LENGTH:
                        current_chunk += part
                    else:
                        if current_chunk.strip():
                            final_sentences.append(current_chunk.strip())
                        current_chunk = part

                if current_chunk.strip():
                    final_sentences.append(current_chunk.strip())

        return final_sentences


class GenerationPredictor:
    """
    Predice tiempos de generación basándose en métricas históricas.
    Usa ventana deslizante de últimas N generaciones para mejor precisión.
    """

    def __init__(self, window_size: int = 20):
        """
        Args:
            window_size: Número de métricas a mantener en historial
        """
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)

        # Métricas por defecto (basadas en benchmarks iniciales)
        self.default_chars_per_second = 4.5  # Promedio de tus logs
        self.default_base_overhead_ms = 2000  # Overhead de inicialización

    def record_generation(self, text_length: int, duration_ms: float):
        """
        Registra una generación completada para mejorar predicciones.

        Args:
            text_length: Longitud del texto en caracteres
            duration_ms: Tiempo que tomó generar en milisegundos
        """
        if text_length > 0 and duration_ms > 0:
            chars_per_second = (text_length / (duration_ms / 1000))
            self.history.append({
                'text_length': text_length,
                'duration_ms': duration_ms,
                'chars_per_second': chars_per_second
            })
            logger.debug(f"Recorded: {text_length} chars in {duration_ms:.2f}ms ({chars_per_second:.2f} cps)")

    def predict_duration(self, text_length: int) -> float:
        """
        Predice tiempo de generación para un texto de cierta longitud.

        Args:
            text_length: Longitud del texto en caracteres

        Returns:
            Tiempo estimado en milisegundos
        """
        if not self.history:
            # Sin historial, usar valores por defecto
            estimated_seconds = text_length / self.default_chars_per_second
            return (estimated_seconds * 1000) + self.default_base_overhead_ms

        # Calcular promedio de chars_per_second de las últimas generaciones
        avg_cps = sum(h['chars_per_second'] for h in self.history) / len(self.history)

        # Calcular overhead promedio
        avg_overhead = sum(
            h['duration_ms'] - (h['text_length'] / h['chars_per_second'] * 1000)
            for h in self.history
        ) / len(self.history)

        estimated_seconds = text_length / avg_cps
        predicted_ms = (estimated_seconds * 1000) + avg_overhead

        logger.debug(f"Predicted: {text_length} chars → {predicted_ms:.2f}ms (avg_cps={avg_cps:.2f})")
        return max(predicted_ms, 100)  # Mínimo 100ms

    def get_stats(self) -> Dict:
        """Retorna estadísticas del predictor."""
        if not self.history:
            return {
                'samples': 0,
                'avg_chars_per_second': self.default_chars_per_second,
                'using_defaults': True
            }

        return {
            'samples': len(self.history),
            'avg_chars_per_second': sum(h['chars_per_second'] for h in self.history) / len(self.history),
            'min_chars_per_second': min(h['chars_per_second'] for h in self.history),
            'max_chars_per_second': max(h['chars_per_second'] for h in self.history),
            'using_defaults': False
        }


class ConversationTTS:
    """
    Motor de TTS optimizado para conversaciones en tiempo real.

    Características:
    - Streaming de audio por oraciones
    - Procesamiento paralelo de múltiples chunks
    - Predicción de tiempos
    - Caché de frases comunes
    """

    def __init__(self, tts_engine, max_parallel: int = 2):
        """
        Args:
            tts_engine: Motor TTS subyacente (EngineHTTP)
            max_parallel: Máximo de oraciones a procesar en paralelo
        """
        self.engine = tts_engine
        self.max_parallel = max_parallel
        self.predictor = GenerationPredictor()
        self.cache: Dict[str, bytes] = {}  # Caché simple en memoria

        logger.info(f"ConversationTTS initialized (max_parallel={max_parallel})")

    def _cache_key(self, text: str, emotion: str) -> str:
        """Genera clave única para caché."""
        return f"{emotion}:{text.lower().strip()}"

    async def _generate_single(self, chunk: SentenceChunk) -> AudioChunk:
        """
        Genera audio para una sola oración.

        Args:
            chunk: Chunk de texto a procesar

        Returns:
            AudioChunk con el audio generado
        """
        cache_key = self._cache_key(chunk.text, chunk.emotion)
        start_time = time.time()

        # Verificar caché
        if cache_key in self.cache:
            logger.info(f"Cache HIT: '{chunk.text[:30]}...'")
            return AudioChunk(
                audio_bytes=self.cache[cache_key],
                sentence_index=chunk.index,
                duration_ms=0,  # Instantáneo desde caché
                text=chunk.text,
                emotion=chunk.emotion
            )

        # Generar audio
        logger.info(f"Generating chunk {chunk.index}: '{chunk.text[:50]}...' ({len(chunk.text)} chars)")

        try:
            # Run synchronous synthesize in thread pool
            audio_bytes = await asyncio.to_thread(
                self.engine.synthesize,
                text=chunk.text,
                emotion=chunk.emotion
            )

            duration_ms = (time.time() - start_time) * 1000

            # Registrar métricas
            self.predictor.record_generation(len(chunk.text), duration_ms)

            # Guardar en caché si es corto (frases comunes)
            if len(chunk.text) < 50:
                self.cache[cache_key] = audio_bytes
                logger.debug(f"Cached: '{chunk.text}'")

            return AudioChunk(
                audio_bytes=audio_bytes,
                sentence_index=chunk.index,
                duration_ms=duration_ms,
                text=chunk.text,
                emotion=chunk.emotion
            )

        except Exception as e:
            logger.error(f"Error generating chunk {chunk.index}: {e}")
            raise

    async def synthesize_streaming(
        self,
        text: str,
        emotion: str = "neutral"
    ) -> AsyncGenerator[AudioChunk, None]:
        """
        Genera audio en streaming, emitiendo chunks apenas estén listos.

        Args:
            text: Texto completo a sintetizar
            emotion: Emoción a aplicar

        Yields:
            AudioChunk: Chunks de audio conforme se generan
        """
        # Dividir en oraciones
        sentences = SentenceSplitter.split(text)
        logger.info(f"Split into {len(sentences)} sentences")

        if not sentences:
            return

        # Crear chunks con predicciones
        chunks = []
        for i, sentence in enumerate(sentences):
            estimated_duration = self.predictor.predict_duration(len(sentence))
            chunks.append(SentenceChunk(
                text=sentence,
                emotion=emotion,
                index=i,
                estimated_duration_ms=estimated_duration
            ))

        # Procesar en paralelo con límite
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def process_chunk(chunk: SentenceChunk) -> AudioChunk:
            async with semaphore:
                return await self._generate_single(chunk)

        # Crear tareas
        tasks = [asyncio.create_task(process_chunk(chunk)) for chunk in chunks]

        # Yield resultados en orden conforme se completan
        completed_indices = set()
        pending_results = {}

        while len(completed_indices) < len(chunks):
            # Esperar a que se complete al menos una tarea
            done, pending = await asyncio.wait(
                [t for t in tasks if not t.done()],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=0.1
            )

            # Procesar tareas completadas
            for task in tasks:
                if task.done() and id(task) not in completed_indices:
                    result = await task
                    pending_results[result.sentence_index] = result
                    completed_indices.add(id(task))

            # Yield resultados en orden
            next_index = len([r for r in pending_results.values() if r.sentence_index < min(pending_results.keys(), default=0)])
            while next_index in pending_results:
                yield pending_results[next_index]
                del pending_results[next_index]
                next_index += 1

    async def synthesize_streaming_optimized(
        self,
        text: str,
        emotion: str = "neutral",
        max_words_per_chunk: int = 10
    ) -> AsyncGenerator[AudioChunk, None]:
        """
        Genera audio en streaming optimizado para baja latencia (modo streamer).

        Usa segmentación inteligente por comas con fusión para minimizar
        tiempo hasta primer audio (TTFA).

        Args:
            text: Texto completo a sintetizar
            emotion: Emoción a aplicar
            max_words_per_chunk: Máximo de palabras por chunk

        Yields:
            AudioChunk: Chunks de audio conforme se generan (en orden)

        Example:
            "Hola, me llamo Casiopy, mucho gusto mi gente!"
            → Chunk 1: "Hola, me llamo Casiopy," (4 palabras, ~6s)
            → Chunk 2: "mucho gusto mi gente!" (4 palabras, ~6s)
            Total: ~12s, pero primer audio en ~6s
        """
        # Dividir con estrategia inteligente
        segments = SentenceSplitter.split_for_streaming(text, max_words=max_words_per_chunk)
        logger.info(
            f"Split into {len(segments)} optimized segments",
            total_words=SentenceSplitter.count_words(text),
            max_words_per_chunk=max_words_per_chunk
        )

        if not segments:
            return

        # Crear chunks
        chunks = []
        for i, segment in enumerate(segments):
            word_count = SentenceSplitter.count_words(segment)
            estimated_duration = self.predictor.predict_duration(len(segment))

            chunks.append(SentenceChunk(
                text=segment,
                emotion=emotion,
                index=i,
                estimated_duration_ms=estimated_duration
            ))

            logger.debug(
                f"Chunk {i}: '{segment[:40]}...' ({word_count} words, est. {estimated_duration:.0f}ms)"
            )

        # Generar chunks SECUENCIALMENTE para streaming (uno a la vez)
        # Esto permite que el primer chunk se reproduzca mientras se genera el segundo
        for chunk in chunks:
            result = await self._generate_single(chunk)
            yield result

    async def synthesize_complete(self, text: str, emotion: str = "neutral") -> bytes:
        """
        Genera audio completo (modo tradicional) pero usando procesamiento paralelo.

        Args:
            text: Texto completo
            emotion: Emoción

        Returns:
            Audio completo concatenado
        """
        audio_parts = []

        async for chunk in self.synthesize_streaming(text, emotion):
            audio_parts.append(chunk.audio_bytes)

        # Concatenar todos los chunks de audio
        # Nota: Esto es simplificado, idealmente usar una librería de audio
        # para concatenar WAV correctamente
        return b"".join(audio_parts)

    async def synthesize_complete_optimized(
        self,
        text: str,
        emotion: str = "neutral",
        max_words_per_chunk: int = 10
    ) -> bytes:
        """
        Genera audio completo usando segmentación optimizada (modo youtuber).

        Args:
            text: Texto completo
            emotion: Emoción
            max_words_per_chunk: Máximo de palabras por chunk

        Returns:
            Audio completo concatenado
        """
        audio_parts = []

        async for chunk in self.synthesize_streaming_optimized(text, emotion, max_words_per_chunk):
            audio_parts.append(chunk.audio_bytes)

        return b"".join(audio_parts)

    def get_predictor_stats(self) -> Dict:
        """Retorna estadísticas del predictor."""
        return self.predictor.get_stats()

    def clear_cache(self):
        """Limpia el caché de frases."""
        cache_size = len(self.cache)
        self.cache.clear()
        logger.info(f"Cache cleared ({cache_size} entries)")
