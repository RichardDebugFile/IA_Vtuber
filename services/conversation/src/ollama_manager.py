"""Ollama manager - Verifica y gestiona el servidor Ollama."""
from __future__ import annotations

import os
import subprocess
import time
from typing import Optional

import httpx


class OllamaManager:
    """Manages Ollama server connectivity and model availability."""

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "gemma3",
        timeout: float = 5.0,
    ):
        """Initialize Ollama manager.

        Args:
            host: Ollama server URL
            model: Model name to verify
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.model = model
        self.timeout = timeout

    async def is_server_running(self) -> bool:
        """Check if Ollama server is running.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.host)
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def is_model_available(self) -> bool:
        """Check if the configured model is available.

        Returns:
            True if model is available, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.host}/api/tags")
                if response.status_code != 200:
                    return False

                data = response.json()
                models = [m["name"] for m in data.get("models", [])]

                # Check for exact match or partial match (gemma3 could be gemma3:latest)
                return any(
                    self.model in model_name or model_name.startswith(f"{self.model}:")
                    for model_name in models
                )
        except Exception:
            return False

    async def wait_for_server(self, max_wait: float = 30.0) -> bool:
        """Wait for Ollama server to become available.

        Args:
            max_wait: Maximum time to wait in seconds

        Returns:
            True if server became available, False if timeout
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if await self.is_server_running():
                return True
            await asyncio.sleep(1.0)
        return False

    def try_start_server(self) -> bool:
        """Attempt to start Ollama server.

        Note: This is platform-dependent and may not work in all environments.

        Returns:
            True if start command was executed, False otherwise
        """
        try:
            # Try to start Ollama in background
            # This assumes 'ollama serve' is in PATH
            if os.name == "nt":  # Windows
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                )
            else:  # Unix-like
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            return True
        except FileNotFoundError:
            # ollama command not found
            return False
        except Exception:
            return False

    async def ensure_ready(self, auto_start: bool = True) -> tuple[bool, str]:
        """Ensure Ollama is ready with the required model.

        Args:
            auto_start: Whether to attempt auto-starting Ollama

        Returns:
            Tuple of (ready, message)
            - ready: True if Ollama is ready to use
            - message: Status message
        """
        # Check if server is running
        if not await self.is_server_running():
            if auto_start:
                # Try to start server
                if self.try_start_server():
                    # Wait for it to come online
                    if await self.wait_for_server(max_wait=15.0):
                        pass  # Server started successfully
                    else:
                        return False, f"Ollama server started but didn't become ready in 15s. Check manually at {self.host}"
                else:
                    return False, f"Ollama not running and auto-start failed. Start manually: 'ollama serve'"
            else:
                return False, f"Ollama server not running at {self.host}. Start it with: 'ollama serve'"

        # Server is running, check model
        if not await self.is_model_available():
            return False, f"Model '{self.model}' not found. Pull it with: 'ollama pull {self.model}'"

        return True, f"Ollama ready with model '{self.model}'"


import asyncio


async def main():
    """Test Ollama manager."""
    manager = OllamaManager(
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        model=os.getenv("OLLAMA_MODEL", "gemma3"),
    )

    print(f"Checking Ollama at {manager.host}...")

    ready, message = await manager.ensure_ready(auto_start=True)
    print(f"Ready: {ready}")
    print(f"Message: {message}")


if __name__ == "__main__":
    asyncio.run(main())
