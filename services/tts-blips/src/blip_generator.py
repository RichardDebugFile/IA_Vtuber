"""Synthesize dialogue blips with female voice characteristics."""
from __future__ import annotations

import io
import struct
import wave
from typing import List, Tuple

import numpy as np
from scipy import signal

from src.voice_config import VoiceProfile, get_voice_for_emotion


class BlipGenerator:
    """Generate dialogue blips using additive synthesis."""

    def __init__(self, sample_rate: int = 44100):
        """Initialize blip generator.

        Args:
            sample_rate: Audio sample rate in Hz (default: 44100)
        """
        self.sample_rate = sample_rate

    def _generate_blip_waveform(
        self,
        voice: VoiceProfile,
        char: str = "a"
    ) -> np.ndarray:
        """Generate a single blip waveform using formant synthesis.

        This creates a synthetic vocal-like sound by combining:
        1. Fundamental frequency (pitch)
        2. Formant frequencies (vocal tract resonances)
        3. ADSR envelope (attack-decay-sustain-release)

        Args:
            voice: Voice profile with pitch, formants, duration, etc.
            char: Character being spoken (affects slight variations)

        Returns:
            numpy array of audio samples (mono, float32, range -1 to 1)
        """
        duration_sec = voice.duration_ms / 1000.0
        num_samples = int(duration_sec * self.sample_rate)

        # Time array
        t = np.linspace(0, duration_sec, num_samples, endpoint=False)

        # 1. Generate fundamental frequency (pitch)
        # Use sawtooth wave for richer harmonics (more voice-like than sine)
        fundamental = signal.sawtooth(2 * np.pi * voice.base_pitch * t, width=0.5)

        # 2. Add harmonics at formant frequencies
        # Formants are resonant frequencies that give voices their unique color
        # Female voices have higher formants than male voices

        # First formant (vowel openness) - strongest
        formant1 = 0.6 * np.sin(2 * np.pi * voice.formant_f1 * t)

        # Second formant (vowel frontness) - medium strength
        formant2 = 0.3 * np.sin(2 * np.pi * voice.formant_f2 * t)

        # Third formant (voice quality) - subtle
        formant3 = 0.1 * np.sin(2 * np.pi * voice.formant_f3 * t)

        # Combine fundamental + formants
        waveform = fundamental + formant1 + formant2 + formant3

        # 3. Apply ADSR envelope for natural sound
        envelope = self._create_envelope(
            num_samples,
            attack_samples=int((voice.attack_ms / 1000.0) * self.sample_rate),
            release_samples=int((voice.release_ms / 1000.0) * self.sample_rate),
        )
        waveform = waveform * envelope

        # 4. Normalize and apply amplitude
        waveform = waveform / np.max(np.abs(waveform)) * voice.amplitude

        # 5. Apply slight variation based on character
        # Vowels vs consonants have different spectral characteristics
        char_lower = char.lower()
        if char_lower in "aeiouáéíóú":
            # Vowels: boost formants
            waveform *= 1.1
        elif char_lower in "szcfvñ":
            # Fricatives: add noise component
            noise = np.random.normal(0, 0.05, num_samples)
            waveform = 0.7 * waveform + 0.3 * noise

        return waveform.astype(np.float32)

    def _create_envelope(
        self,
        num_samples: int,
        attack_samples: int,
        release_samples: int,
    ) -> np.ndarray:
        """Create ADSR envelope for natural blip shaping.

        Args:
            num_samples: Total number of samples
            attack_samples: Number of samples for attack (fade in)
            release_samples: Number of samples for release (fade out)

        Returns:
            Envelope array (values 0.0 to 1.0)
        """
        envelope = np.ones(num_samples)

        # Attack (fade in)
        if attack_samples > 0:
            attack = np.linspace(0, 1, min(attack_samples, num_samples))
            envelope[:len(attack)] = attack

        # Release (fade out)
        if release_samples > 0:
            release = np.linspace(1, 0, min(release_samples, num_samples))
            envelope[-len(release):] = release

        return envelope

    def generate_text_blips(
        self,
        text: str,
        emotion: str = "neutral",
        blips_per_second: float = 20.0,
        silence_duration_ms: float = 100.0,
    ) -> Tuple[bytes, int, int]:
        """Generate blip sequence for entire text.

        Args:
            text: Text to generate blips for
            emotion: Emotion name for voice modulation
            blips_per_second: Speed of blips (default: 20 = 50ms between blips)
            silence_duration_ms: Silence added after spaces/punctuation

        Returns:
            Tuple of (wav_bytes, total_duration_ms, num_blips)
        """
        # Get emotion-modulated voice
        voice = get_voice_for_emotion(emotion)

        # Calculate inter-blip silence
        blip_interval_ms = 1000.0 / blips_per_second
        silence_between_ms = max(0, blip_interval_ms - voice.duration_ms)

        # Generate blips for each character
        audio_segments: List[np.ndarray] = []
        num_blips = 0

        for char in text:
            if char.isspace():
                # Add longer silence for spaces
                silence_samples = int((silence_duration_ms / 1000.0) * self.sample_rate)
                audio_segments.append(np.zeros(silence_samples, dtype=np.float32))
            elif char in ".,;:!?¡¿":
                # Punctuation: slight pause
                pause_samples = int((silence_duration_ms * 0.5 / 1000.0) * self.sample_rate)
                audio_segments.append(np.zeros(pause_samples, dtype=np.float32))
            else:
                # Generate blip for this character
                blip = self._generate_blip_waveform(voice, char)
                audio_segments.append(blip)
                num_blips += 1

                # Add inter-blip silence
                if silence_between_ms > 0:
                    silence_samples = int((silence_between_ms / 1000.0) * self.sample_rate)
                    audio_segments.append(np.zeros(silence_samples, dtype=np.float32))

        # Concatenate all segments
        if not audio_segments:
            # Empty text
            full_audio = np.zeros(0, dtype=np.float32)
        else:
            full_audio = np.concatenate(audio_segments)

        # Convert to WAV bytes
        wav_bytes = self._to_wav_bytes(full_audio)
        total_duration_ms = int((len(full_audio) / self.sample_rate) * 1000)

        return wav_bytes, total_duration_ms, num_blips

    def generate_single_blip(
        self,
        char: str = "a",
        emotion: str = "neutral",
    ) -> bytes:
        """Generate a single blip for preview/testing.

        Args:
            char: Character to generate blip for
            emotion: Emotion for voice modulation

        Returns:
            WAV audio bytes
        """
        voice = get_voice_for_emotion(emotion)
        blip = self._generate_blip_waveform(voice, char)
        return self._to_wav_bytes(blip)

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert numpy audio to WAV bytes.

        Args:
            audio: Audio samples (float32, mono, range -1 to 1)

        Returns:
            WAV file bytes
        """
        # Convert float32 to int16 for WAV
        audio_int16 = (audio * 32767).astype(np.int16)

        # Write to WAV format in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return wav_buffer.getvalue()
