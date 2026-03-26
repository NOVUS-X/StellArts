from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class IngestionConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        session_connections = self._connections.get(session_id)
        if not session_connections:
            return

        session_connections.discard(websocket)
        if not session_connections:
            self._connections.pop(session_id, None)

    async def publish(self, session_id: str | None, message: dict) -> None:
        if not session_id:
            return

        for websocket in list(self._connections.get(session_id, set())):
            await websocket.send_json(message)


ingestion_connection_manager = IngestionConnectionManager()
