"""Audio processing utilities for dataset generation."""

import io
import soundfile as sf
import numpy as np
from scipy import signal
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Process audio files to meet dataset specifications."""

    TARGET_SAMPLE_RATE = 24000
    TARGET_BIT_DEPTH = 'PCM_16'
    TARGET_DB = -3.0

    @staticmethod
    def normalize_audio(audio_data: np.ndarray, target_db: float = -3.0) -> np.ndarray:
        """
        Normalize audio to target dB peak.

        Args:
            audio_data: Audio samples as numpy array
            target_db: Target peak level in dB (default: -3.0)

        Returns:
            Normalized audio data
        """
        peak = np.max(np.abs(audio_data))

        if peak == 0:
            logger.warning("Audio has zero peak, cannot normalize")
            return audio_data

        # Convert dB to linear scale
        target_peak = 10 ** (target_db / 20.0)

        # Normalize to target peak
        normalized = audio_data * (target_peak / peak)

        logger.debug(f"Normalized audio from peak {peak:.4f} to {target_peak:.4f}")
        return normalized

    @staticmethod
    def resample_to_24khz(audio_data: np.ndarray, original_sr: int) -> np.ndarray:
        """
        Resample audio to 24kHz.

        Args:
            audio_data: Audio samples
            original_sr: Original sample rate

        Returns:
            Resampled audio data at 24kHz
        """
        if original_sr == 24000:
            return audio_data

        logger.debug(f"Resampling from {original_sr}Hz to 24000Hz")

        # Calculate resampling ratio
        ratio = 24000 / original_sr
        num_samples = int(len(audio_data) * ratio)

        # Resample using scipy
        resampled = signal.resample(audio_data, num_samples)

        return resampled

    @staticmethod
    def to_mono(audio_data: np.ndarray) -> np.ndarray:
        """
        Convert stereo audio to mono.

        Args:
            audio_data: Audio samples (can be mono or stereo)

        Returns:
            Mono audio data
        """
        if len(audio_data.shape) == 1:
            # Already mono
            return audio_data

        if len(audio_data.shape) == 2:
            # Stereo - average channels
            logger.debug("Converting stereo to mono")
            return np.mean(audio_data, axis=1)

        raise ValueError(f"Unexpected audio shape: {audio_data.shape}")

    @staticmethod
    async def process_and_save(
        audio_bytes: bytes,
        output_path: Path,
        target_db: float = -3.0
    ) -> dict:
        """
        Process audio bytes and save with correct specifications.

        This method:
        1. Loads audio from bytes
        2. Converts to mono if stereo
        3. Resamples to 24kHz
        4. Normalizes to target dB peak
        5. Saves as 16-bit WAV

        Args:
            audio_bytes: Raw audio data
            output_path: Where to save the processed audio
            target_db: Target peak level in dB

        Returns:
            Dictionary with duration_seconds and file_size_kb
        """
        try:
            # Load audio from bytes
            audio_data, sr = sf.read(io.BytesIO(audio_bytes))
            logger.info(f"Loaded audio: {len(audio_data)} samples at {sr}Hz")

            # Convert to mono
            audio_data = AudioProcessor.to_mono(audio_data)

            # Resample to 24kHz
            audio_data = AudioProcessor.resample_to_24khz(audio_data, sr)

            # Normalize to target dB
            audio_data = AudioProcessor.normalize_audio(audio_data, target_db)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as 16-bit WAV at 24kHz
            sf.write(
                str(output_path),
                audio_data,
                AudioProcessor.TARGET_SAMPLE_RATE,
                subtype=AudioProcessor.TARGET_BIT_DEPTH
            )

            # Calculate metadata
            duration = len(audio_data) / AudioProcessor.TARGET_SAMPLE_RATE
            file_size = output_path.stat().st_size

            logger.info(
                f"Saved audio: {output_path.name} "
                f"({duration:.2f}s, {file_size // 1024}KB)"
            )

            return {
                "duration_seconds": round(duration, 2),
                "file_size_kb": file_size // 1024
            }

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            raise

    @staticmethod
    def validate_audio(file_path: Path) -> Tuple[bool, str]:
        """
        Validate that audio file meets specifications.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            info = sf.info(str(file_path))

            # Check sample rate
            if info.samplerate != AudioProcessor.TARGET_SAMPLE_RATE:
                return False, f"Invalid sample rate: {info.samplerate}Hz (expected 24000Hz)"

            # Check channels
            if info.channels != 1:
                return False, f"Invalid channels: {info.channels} (expected 1/mono)"

            # Check bit depth
            if info.subtype != AudioProcessor.TARGET_BIT_DEPTH:
                return False, f"Invalid bit depth: {info.subtype} (expected PCM_16)"

            # Check duration (3-10 seconds)
            duration = info.frames / info.samplerate
            if not (3.0 <= duration <= 10.0):
                return False, f"Invalid duration: {duration:.2f}s (expected 3-10s)"

            return True, "Valid"

        except Exception as e:
            return False, f"Validation error: {e}"
