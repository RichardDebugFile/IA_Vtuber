"""Whisper transcription engine."""
import logging
from typing import Optional, List, Dict, Any
import numpy as np

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None

from .config import (
    WHISPER_MODEL,
    DEVICE,
    LANGUAGE,
    COMPUTE_TYPE,
    BEAM_SIZE,
    BEST_OF,
    TEMPERATURE,
    SAMPLE_RATE,
)

logger = logging.getLogger(__name__)


class Transcriber:
    """Speech-to-text transcription using Faster Whisper."""

    def __init__(self):
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper not available. Install with: pip install faster-whisper"
            )

        logger.info(f"Loading Whisper model: {WHISPER_MODEL} on device: {DEVICE}")

        # Determine best compute type for device
        actual_device = DEVICE
        actual_compute_type = COMPUTE_TYPE

        # Auto-detect best compute type
        if DEVICE == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    actual_device = "cuda"
                    # Use float16 for modern NVIDIA GPUs (Blackwell, Ada, Ampere, etc.)
                    actual_compute_type = "float16"
                    logger.info("CUDA detected: using float16 compute type")
                else:
                    actual_device = "cpu"
                    actual_compute_type = "float32"
                    logger.info("CPU mode: using float32 compute type")
            except ImportError:
                actual_device = "cpu"
                actual_compute_type = "float32"
                logger.info("PyTorch not available, defaulting to CPU with float32")
        elif DEVICE == "cuda":
            # Force float16 for CUDA to ensure compatibility with modern GPUs
            actual_compute_type = "float16"
            logger.info("CUDA mode: forcing float16 for GPU compatibility")

        logger.info(f"Final config: device={actual_device}, compute_type={actual_compute_type}")

        # Load Whisper model
        self.model = WhisperModel(
            WHISPER_MODEL,
            device=actual_device,
            compute_type=actual_compute_type,
            download_root=None,  # Use default cache
        )

        self.default_language = LANGUAGE if LANGUAGE != "auto" else None
        logger.info(f"Whisper model loaded successfully. Default language: {self.default_language or 'auto-detect'}")

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        include_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono, 16kHz)
            language: Language code (e.g., 'es', 'en') or None for auto-detect
            include_timestamps: Include word-level timestamps

        Returns:
            Dictionary with transcription results:
            {
                "text": str,
                "language": str,
                "duration": float,
                "segments": List[Dict],
            }
        """
        # Ensure audio is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize audio to [-1.0, 1.0] range
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / max(abs(audio.max()), abs(audio.min()))

        # Use provided language or default
        lang = language or self.default_language

        # Transcribe
        segments, info = self.model.transcribe(
            audio,
            language=lang,
            beam_size=BEAM_SIZE,
            best_of=BEST_OF,
            temperature=TEMPERATURE,
            vad_filter=True,  # Enable voice activity detection
            word_timestamps=include_timestamps,
        )

        # Collect segments
        result_segments = []
        full_text = []

        for segment in segments:
            seg_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }

            if include_timestamps and hasattr(segment, "words") and segment.words:
                seg_dict["words"] = [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    }
                    for w in segment.words
                ]

            result_segments.append(seg_dict)
            full_text.append(segment.text.strip())

        # Calculate duration
        duration = result_segments[-1]["end"] if result_segments else 0.0

        return {
            "text": " ".join(full_text),
            "language": info.language,
            "duration": duration,
            "segments": result_segments,
            "language_probability": info.language_probability,
        }

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        include_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code or None for auto-detect
            include_timestamps: Include word-level timestamps

        Returns:
            Dictionary with transcription results
        """
        import soundfile as sf
        from pathlib import Path

        try:
            # Try to load audio file directly
            audio, sr = sf.read(audio_path, dtype="float32")
        except Exception as e:
            # If soundfile fails, try converting with ffmpeg (for WebM, etc.)
            logger.warning(f"soundfile failed to read {audio_path}: {e}, trying ffmpeg conversion")

            try:
                import subprocess
                import tempfile

                # Convert to WAV using ffmpeg
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                    tmp_wav_path = tmp_wav.name

                # Use ffmpeg to convert to standard WAV
                subprocess.run(
                    [
                        "ffmpeg",
                        "-i", audio_path,
                        "-ar", str(SAMPLE_RATE),
                        "-ac", "1",  # Mono
                        "-f", "wav",
                        tmp_wav_path,
                        "-y"  # Overwrite
                    ],
                    check=True,
                    capture_output=True
                )

                # Read converted file
                audio, sr = sf.read(tmp_wav_path, dtype="float32")

                # Clean up
                Path(tmp_wav_path).unlink(missing_ok=True)

            except Exception as ffmpeg_error:
                logger.error(f"ffmpeg conversion failed: {ffmpeg_error}")
                raise RuntimeError(
                    f"Could not read audio file. Tried soundfile and ffmpeg. "
                    f"Original error: {e}, ffmpeg error: {ffmpeg_error}"
                )

        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        # Resample if needed
        if sr != SAMPLE_RATE:
            import scipy.signal
            num_samples = int(len(audio) * SAMPLE_RATE / sr)
            audio = scipy.signal.resample(audio, num_samples)

        return self.transcribe(audio, language, include_timestamps)
