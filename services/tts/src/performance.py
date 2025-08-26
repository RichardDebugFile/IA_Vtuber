"""Utility class to benchmark the TTS pipeline."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .engine import TTSEngine
from .conversation_client import ConversationClient

@dataclass
class TTSPerformance:
    """Small helper to measure end-to-end generation time."""
    engine: TTSEngine
    conv: ConversationClient

    async def run(self, text: str) -> float:
        """Return the time taken (in seconds) to obtain audio for ``text``."""
        start = time.perf_counter()
        reply, emotion = await self.conv.ask(text)
        self.engine.synthesize(reply, emotion)
        return time.perf_counter() - start
