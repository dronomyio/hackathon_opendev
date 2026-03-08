"""
ChessEcon Backend — WebSocket Event Bus
Broadcasts real-time game events, training metrics, and economy updates
to all connected frontend clients.
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from shared.models import WSEvent, EventType

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event: WSEvent) -> None:
        """Send an event to all connected clients."""
        if not self._connections:
            return
        payload = event.model_dump_json()
        dead: Set[WebSocket] = set()
        async with self._lock:
            connections = set(self._connections)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._connections -= dead

    async def broadcast_raw(self, data: dict) -> None:
        """Broadcast a raw dict, preserving the 'type' field from the dict itself."""
        type_map = {
            "game_start": EventType.GAME_START,
            "move": EventType.MOVE,
            "coaching_request": EventType.COACHING_REQUEST,
            "coaching_result": EventType.COACHING_RESULT,
            "game_end": EventType.GAME_END,
            "training_step": EventType.TRAINING_STEP,
            "economy_update": EventType.ECONOMY_UPDATE,
        }
        event_type = type_map.get(data.get("type", ""), EventType.MOVE)
        event = WSEvent(type=event_type, data=data.get("data", data))
        await self.broadcast(event)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# ── Helper functions for emitting typed events ────────────────────────────────

async def emit_game_start(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.GAME_START, data=data))

async def emit_move(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.MOVE, data=data))

async def emit_coaching_request(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.COACHING_REQUEST, data=data))

async def emit_coaching_result(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.COACHING_RESULT, data=data))

async def emit_game_end(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.GAME_END, data=data))

async def emit_training_step(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.TRAINING_STEP, data=data))

async def emit_economy_update(manager: ConnectionManager, data: dict) -> None:
    await manager.broadcast(WSEvent(type=EventType.ECONOMY_UPDATE, data=data))


# Singleton
ws_manager = ConnectionManager()
