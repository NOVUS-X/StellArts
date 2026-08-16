import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps user_id -> list of active WebSocket connections
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user_id={user_id}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user_id={user_id}")

    async def send_personal_message(self, data: dict, user_id: int):
        if user_id not in self.active_connections:
            return

        dead_sockets = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Error sending WS message to user {user_id}: {e}")
                dead_sockets.append(connection)

        for dead_socket in dead_sockets:
            self.disconnect(dead_socket, user_id)


manager = ConnectionManager()
