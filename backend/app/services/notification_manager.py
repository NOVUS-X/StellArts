import json
from typing import Dict
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session


class ConnectionManager:
    def __init__(self):
        # user_id: WebSocket
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            await websocket.send_json(message)

    async def send_notification(self, notification, user_id: int):
        message = {
            "type": "notification",
            "data": {
                "id": str(notification.id),
                "user_id": notification.user_id,
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "read": notification.is_read,
                "reference_id": str(notification.reference_id) if notification.reference_id else None,
                "created_at": notification.created_at.isoformat(),
                "updated_at": notification.updated_at.isoformat(),
            }
        }
        await self.send_personal_message(message, user_id)


manager = ConnectionManager()
