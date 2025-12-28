"""
Cliente Fish Speech con voz centralizada de Casiopy

Este módulo proporciona una interfaz simplificada para usar Fish Speech
con la voz pre-configurada de Casiopy, eliminando la necesidad de especificar
referencias de audio en cada llamada.

Uso:
    from fish_client_casiopy import CasiopyTTSClient

    client = CasiopyTTSClient()
    client.synthesize("Hola mundo", "output.wav")
"""

import httpx
import logging
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger(__name__)


class CasiopyTTSClient:
    """
    Cliente TTS con voz de Casiopy centralizada

    Attributes:
        base_url: URL base del servicio Fish Speech (default: http://localhost:8080)
        reference_id: ID de la referencia de voz (default: "casiopy")
        timeout: Timeout para requests HTTP en segundos (default: 60)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        reference_id: str = "casiopy",
        timeout: float = 60.0
    ):
        """
        Inicializa el cliente TTS con voz de Casiopy

        Args:
            base_url: URL del servicio Fish Speech
            reference_id: ID de la carpeta de referencias en /workspace/fish-speech/references/
            timeout: Timeout para requests en segundos
        """
        self.base_url = base_url.rstrip("/")
        self.reference_id = reference_id
        self.client = httpx.Client(timeout=timeout)

        logger.info(f"CasiopyTTSClient initialized: {self.base_url}, voice: {reference_id}")

    def synthesize(
        self,
        text: str,
        output_path: str | Path,
        format: Literal["wav", "pcm", "mp3"] = "wav",
        add_ellipsis: bool = True,
        chunk_length: int = 200,
        normalize: bool = True,
        temperature: float = 0.7,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        seed: Optional[int] = None
    ) -> bool:
        """
        Sintetiza texto a audio usando la voz de Casiopy

        Args:
            text: Texto a sintetizar
            output_path: Ruta donde guardar el archivo de audio
            format: Formato de audio (wav, pcm, mp3)
            add_ellipsis: Agregar '...' al final para evitar cortes (recomendado)
            chunk_length: Longitud de chunks para procesamiento (100-300)
            normalize: Normalizar texto para números (recomendado para estabilidad)
            temperature: Control de creatividad (0.1-1.0)
            top_p: Nucleus sampling (0.1-1.0)
            repetition_penalty: Penalización por repetición (0.9-2.0)
            seed: Semilla para reproducibilidad (opcional)

        Returns:
            True si la síntesis fue exitosa, False en caso contrario

        Raises:
            httpx.HTTPError: Si hay error en la comunicación HTTP
        """
        # Agregar pausa natural al final si está habilitado
        if add_ellipsis and not text.endswith(("...", ".", "!", "?")):
            text += "..."

        # Preparar payload
        payload = {
            "text": text,
            "format": format,
            "reference_id": self.reference_id,
            "chunk_length": chunk_length,
            "normalize": normalize,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "use_memory_cache": "on"  # Cachear referencias para mejor performance
        }

        if seed is not None:
            payload["seed"] = seed

        try:
            logger.info(f"Synthesizing: {text[:50]}...")

            response = self.client.post(
                f"{self.base_url}/v1/tts",
                json=payload
            )
            response.raise_for_status()

            # Guardar audio
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(f"Audio saved: {output_path} ({len(response.content)} bytes)")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def health_check(self) -> bool:
        """
        Verifica si el servicio TTS está disponible

        Returns:
            True si el servicio responde, False en caso contrario
        """
        try:
            response = self.client.get(f"{self.base_url}/v1/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def close(self):
        """Cierra el cliente HTTP"""
        self.client.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class AsyncCasiopyTTSClient:
    """
    Cliente TTS asíncrono con voz de Casiopy centralizada

    Uso:
        async with AsyncCasiopyTTSClient() as client:
            await client.synthesize("Hola", "output.wav")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        reference_id: str = "casiopy",
        timeout: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.reference_id = reference_id
        self.client = httpx.AsyncClient(timeout=timeout)

        logger.info(f"AsyncCasiopyTTSClient initialized: {self.base_url}, voice: {reference_id}")

    async def synthesize(
        self,
        text: str,
        output_path: str | Path,
        format: Literal["wav", "pcm", "mp3"] = "wav",
        add_ellipsis: bool = True,
        chunk_length: int = 200,
        normalize: bool = True,
        temperature: float = 0.7,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        seed: Optional[int] = None
    ) -> bool:
        """Versión asíncrona de synthesize()"""

        if add_ellipsis and not text.endswith(("...", ".", "!", "?")):
            text += "..."

        payload = {
            "text": text,
            "format": format,
            "reference_id": self.reference_id,
            "chunk_length": chunk_length,
            "normalize": normalize,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "use_memory_cache": "on"
        }

        if seed is not None:
            payload["seed"] = seed

        try:
            logger.info(f"Synthesizing (async): {text[:50]}...")

            response = await self.client.post(
                f"{self.base_url}/v1/tts",
                json=payload
            )
            response.raise_for_status()

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(f"Audio saved: {output_path} ({len(response.content)} bytes)")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    async def health_check(self) -> bool:
        """Versión asíncrona de health_check()"""
        try:
            response = await self.client.get(f"{self.base_url}/v1/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self):
        """Cierra el cliente HTTP asíncrono"""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Ejemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Cliente síncrono
    print("=== Cliente Síncrono ===")
    with CasiopyTTSClient() as client:
        # Health check
        if not client.health_check():
            print("❌ Servicio TTS no disponible")
            exit(1)
        print("✅ Servicio TTS disponible")

        # Sintetizar
        success = client.synthesize(
            text="Hola, soy Casiopy. Esta es una prueba de mi voz personalizada",
            output_path="test_casiopy.wav"
        )

        if success:
            print("✅ Audio generado: test_casiopy.wav")
        else:
            print("❌ Error al generar audio")

    # Cliente asíncrono
    print("\n=== Cliente Asíncrono ===")
    import asyncio

    async def async_example():
        async with AsyncCasiopyTTSClient() as client:
            # Health check
            if not await client.health_check():
                print("❌ Servicio TTS no disponible")
                return
            print("✅ Servicio TTS disponible")

            # Sintetizar
            success = await client.synthesize(
                text="Esta es la versión asíncrona de Casiopy",
                output_path="test_casiopy_async.wav"
            )

            if success:
                print("✅ Audio generado: test_casiopy_async.wav")
            else:
                print("❌ Error al generar audio")

    asyncio.run(async_example())
