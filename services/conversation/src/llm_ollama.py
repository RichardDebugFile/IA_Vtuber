import os, httpx
from typing import List, Dict, Any

# Configuración desde .env o variables
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")  

async def list_models() -> list[str]:
    """Devuelve los nombres de modelos instalados en Ollama."""
    async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=10.0) as client:
        r = await client.get("/api/tags")
        r.raise_for_status()
        js = r.json()
        return [m.get("name") for m in js.get("models", []) if m.get("name")]

async def chat(messages: List[Dict[str, str]], *, model: str | None = None, timeout: float = 60.0) -> str:
    """
    Llama a /api/chat de Ollama (no streaming) y devuelve el texto.
    messages = [{"role":"user"/"assistant"/"system","content":"..."}]
    """
    mdl = (model or os.getenv("OLLAMA_MODEL") or OLLAMA_MODEL).strip()
    url = f"{OLLAMA_HOST}/api/chat"
    payload: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        return (data.get("message", {}) or {}).get("content", "").strip()
