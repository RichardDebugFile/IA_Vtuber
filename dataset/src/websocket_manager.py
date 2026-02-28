"""WebSocket connection manager for real-time updates."""

import json
import logging
from typing import List
from fastapi import WebSocket
from .models import WebSocketMessage

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections and broadcast messages."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection.

        Args:
            message: Message data to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: dict):
        """
        Broadcast a message to all connected WebSocket clients.

        Args:
            message: Message data to broadcast
        """
        if not self.active_connections:
            return

        logger.debug(f"Broadcasting to {len(self.active_connections)} connections: {message.get('type')}")

        # Send to all connections, removing failed ones
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_progress(self, completed: int, total: int, failed: int):
        """
        Broadcast progress update.

        Args:
            completed: Number of completed entries
            total: Total number of entries
            failed: Number of failed entries
        """
        message = {
            "type": "progress",
            "data": {
                "completed": completed,
                "total": total,
                "failed": failed,
                "percentage": round((completed / total * 100) if total > 0 else 0, 1)
            }
        }
        await self.broadcast(message)

    async def broadcast_status(self, status: str):
        """
        Broadcast status change.

        Args:
            status: New status (idle, running, paused, stopped, completed)
        """
        message = {
            "type": "status",
            "data": {"status": status}
        }
        await self.broadcast(message)

    async def broadcast_entry_update(self, entry_data: dict):
        """
        Broadcast individual entry update.

        Args:
            entry_data: Entry data dictionary
        """
        message = {
            "type": "entry_update",
            "data": entry_data
        }
        await self.broadcast(message)

    async def broadcast_error(self, error_message: str, entry_id: int = None):
        """
        Broadcast error message.

        Args:
            error_message: Error description
            entry_id: Optional ID of related entry
        """
        message = {
            "type": "error",
            "data": {
                "message": error_message,
                "entry_id": entry_id
            }
        }
        await self.broadcast(message)

    async def broadcast_service_status(self, tts_available: bool, fish_available: bool):
        """
        Broadcast service availability status.

        Args:
            tts_available: Whether TTS service is available
            fish_available: Whether Fish Speech service is available
        """
        message = {
            "type": "service_status",
            "data": {
                "tts_available": tts_available,
                "fish_available": fish_available
            }
        }
        await self.broadcast(message)

    async def broadcast_log(self, message: str, level: str = "info"):
        """
        Broadcast a log message to all connected clients.

        Args:
            message: Log message to broadcast
            level: Log level (info, success, error, warning, generating)
        """
        log_message = {
            "type": "log",
            "data": {
                "message": message,
                "level": level
            }
        }
        await self.broadcast(log_message)

    def get_connection_count(self) -> int:
        """
        Get number of active connections.

        Returns:
            Number of active WebSocket connections
        """
        return len(self.active_connections)
