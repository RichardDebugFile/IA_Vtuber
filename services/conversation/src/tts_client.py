import os
import httpx

TTS_HTTP = os.getenv("TTS_HTTP", "http://127.0.0.1:8802")

async def synthesize(text: str, emotion: str, base_url: str | None = None) -> str:
    """Send text and emotion to the TTS service and return audio in base64."""
    url = f"{base_url or TTS_HTTP}/synthesize"
    payload = {"text": text, "emotion": emotion}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("audio_b64", "")
