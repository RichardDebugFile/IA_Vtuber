"""Voice configuration for female-sounding dialogue blips."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class VoiceProfile:
    """Voice characteristics profile."""

    # Fundamental frequency (pitch) in Hz
    base_pitch: float

    # Formant frequencies (vocal tract resonances) in Hz
    # These create the "color" of the voice
    formant_f1: float  # First formant (vowel openness)
    formant_f2: float  # Second formant (vowel frontness)
    formant_f3: float  # Third formant (voice quality)

    # Blip characteristics
    duration_ms: float  # Duration of each blip
    attack_ms: float    # Attack time (fade in)
    release_ms: float   # Release time (fade out)

    # Amplitude/volume
    amplitude: float    # 0.0 to 1.0


# Female voice profile (based on acoustic phonetics research)
# Female voices have higher pitch and formants than male voices
FEMALE_VOICE = VoiceProfile(
    base_pitch=260.0,      # Hz - higher female F0 for younger, more feminine voice (range: 200-280 Hz)
    formant_f1=850.0,      # Hz - raised first formant for brighter sound
    formant_f2=1400.0,     # Hz - raised second formant (more feminine)
    formant_f3=3200.0,     # Hz - raised third formant (lighter voice quality)
    duration_ms=50.0,      # Shorter, lighter blips
    attack_ms=4.0,         # Very quick attack
    release_ms=8.0,        # Quick release
    amplitude=0.75,        # Slightly louder to compensate for higher pitch
)


# Emotion-based pitch modulation
# Higher pitch = more energetic/positive emotions
# Lower pitch = sadder/calmer emotions
EMOTION_PITCH_MODULATION: Dict[str, float] = {
    # Multiplier applied to base_pitch (base = 260 Hz)
    "neutral": 1.0,      # 260 Hz
    "happy": 1.15,       # 300 Hz - bright and cheerful
    "excited": 1.23,     # 320 Hz - very high, energetic
    "love": 1.08,        # 280 Hz - warm and sweet
    "amused": 1.12,      # 290 Hz
    "playful": 1.15,     # 300 Hz
    "surprised": 1.19,   # 310 Hz - sudden pitch raise
    "confused": 1.04,    # 270 Hz - slightly uncertain
    "thinking": 0.92,    # 240 Hz - lower, contemplative
    "sad": 0.81,         # 210 Hz - lower, subdued
    "bored": 0.85,       # 220 Hz - monotone
    "sleeping": 0.77,    # 200 Hz - very low, drowsy
    "angry": 1.08,       # 280 Hz - tense, sharp
    "upset": 0.92,       # 240 Hz
    "fear": 1.12,        # 290 Hz - anxious pitch raise
    "scared": 1.15,      # 300 Hz
}


# Emotion-based duration modulation
# Shorter = more energetic, Longer = more drawn out
EMOTION_DURATION_MODULATION: Dict[str, float] = {
    "neutral": 1.0,      # 50 ms - base duration
    "happy": 0.80,       # 40 ms - quick, peppy
    "excited": 0.70,     # 35 ms - very fast, energetic
    "love": 1.20,        # 60 ms - slightly drawn out, soft
    "amused": 0.80,      # 40 ms
    "playful": 0.80,     # 40 ms
    "surprised": 0.70,   # 35 ms - quick reaction
    "confused": 1.10,    # 55 ms - hesitant
    "thinking": 1.20,    # 60 ms - slower, thoughtful
    "sad": 1.40,         # 70 ms - slower, lower energy
    "bored": 1.30,       # 65 ms - sluggish
    "sleeping": 1.60,    # 80 ms - very slow, drowsy
    "angry": 0.70,       # 35 ms - sharp, staccato
    "upset": 1.10,       # 55 ms
    "fear": 0.90,        # 45 ms - quick, nervous
    "scared": 0.80,      # 40 ms - tense
}


# Emotion-based amplitude modulation
EMOTION_AMPLITUDE_MODULATION: Dict[str, float] = {
    "neutral": 1.0,      # 0.7
    "happy": 1.14,       # 0.8
    "excited": 1.21,     # 0.85
    "love": 1.0,         # 0.7
    "amused": 1.07,      # 0.75
    "playful": 1.14,     # 0.8
    "surprised": 1.14,   # 0.8
    "confused": 0.86,    # 0.6
    "thinking": 0.86,    # 0.6
    "sad": 0.71,         # 0.5
    "bored": 0.71,       # 0.5
    "sleeping": 0.57,    # 0.4
    "angry": 1.29,       # 0.9
    "upset": 1.0,        # 0.7
    "fear": 1.07,        # 0.75
    "scared": 1.14,      # 0.8
}


def get_voice_for_emotion(emotion: str) -> VoiceProfile:
    """Get a voice profile modulated by emotion.

    Args:
        emotion: Emotion name (e.g., "happy", "sad", "neutral")

    Returns:
        VoiceProfile with emotion-specific modulations
    """
    # Start with base female voice
    base = FEMALE_VOICE

    # Get modulation factors (default to neutral if unknown emotion)
    pitch_mod = EMOTION_PITCH_MODULATION.get(emotion, 1.0)
    duration_mod = EMOTION_DURATION_MODULATION.get(emotion, 1.0)
    amplitude_mod = EMOTION_AMPLITUDE_MODULATION.get(emotion, 1.0)

    # Create modulated profile
    return VoiceProfile(
        base_pitch=base.base_pitch * pitch_mod,
        formant_f1=base.formant_f1,  # Formants stay constant
        formant_f2=base.formant_f2,
        formant_f3=base.formant_f3,
        duration_ms=base.duration_ms * duration_mod,
        attack_ms=base.attack_ms,
        release_ms=base.release_ms,
        amplitude=base.amplitude * amplitude_mod,
    )
