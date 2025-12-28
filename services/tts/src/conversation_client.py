"""Client to interact with the conversation microservice."""
from __future__ import annotations

import os
import httpx
from typing import Tuple

CONVERSATION_HTTP = os.getenv("CONVERSATION_HTTP", "http://127.0.0.1:8801")

class ConversationClient:
    """Simple HTTP client for the conversation service."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or CONVERSATION_HTTP

    async def ask(self, text: str, user: str = "local") -> Tuple[str, str]:
        """Send text to the conversation service and return reply and emotion.

        Args:
            text: User input text
            user: User identifier (default: "local")

        Returns:
            Tuple of (reply, emotion)

        Raises:
            httpx.HTTPStatusError: If the conversation service returns an error
            httpx.TimeoutException: If request takes longer than 30 seconds
        """
        payload = {"user": user, "text": text}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("reply", ""), data.get("emotion", "neutral")
