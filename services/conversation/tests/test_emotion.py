import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from emotion import classify


def test_classify_text_with_accents_returns_fear():
    assert classify("¡Qué pánico!") == "fear"


def test_classify_text_without_accents_returns_fear():
    assert classify("que panico") == "fear"


def test_classify_angry_emoji():
    assert classify("😡") == "angry"
