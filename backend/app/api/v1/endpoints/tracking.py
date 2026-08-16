import asyncio
import json
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.user import RoleEnum

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and Redis Pub/Sub for location tracking."""

    def __init__(self):
        # Maps job_id -> set of WebSocket connections
        self.active_connections: dict[str, set[WebSocket]] = {}
        self.redis: aioredis.Redis | None = None
        self.pubsub_tasks: dict[str, asyncio.Task] = {}

    async def initialize_redis(self):
        """Initialize Redis connection for Pub/Sub."""
        if self.redis is None:
            self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get_redis(self) -> aioredis.Redis:
        """Get Redis connection, initializing if needed."""
        if self.redis is None:
            await self.initialize_redis()
        return self.redis

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept a new WebSocket connection for a specific job."""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            # Clean up empty job entries
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        """Broadcast a message to all connections listening to a job."""
        if job_id in self.active_connections:
            message_str = json.dumps(message)
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_text(message_str)
                except Exception:
                    disconnected.add(connection)
            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections[job_id].discard(conn)

    async def start_pubsub_listener(self, job_id: str):
        """Start listening to Redis Pub/Sub channel for a job."""
        redis = await self.get_redis()
        pubsub = redis.pubsub()
        channel = f"tracking:{job_id}"
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await self.broadcast(job_id, data)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def publish_location(self, job_id: str, location_data: dict):
        """Publish location data to Redis Pub/Sub channel."""
        redis = await self.get_redis()
        channel = f"tracking:{job_id}"
        await redis.publish(channel, json.dumps(location_data))

    def ensure_pubsub_task(self, job_id: str):
        """Ensure a Pub/Sub listener task exists for this job."""
        if job_id not in self.pubsub_tasks or self.pubsub_tasks[job_id].done():
            self.pubsub_tasks[job_id] = asyncio.create_task(
                self.start_pubsub_listener(job_id)
            )

    def cancel_pubsub_task(self, job_id: str):
        """Cancel the Pub/Sub listener task for a job if no more connections."""
        if job_id in self.pubsub_tasks and job_id not in self.active_connections:
            self.pubsub_tasks[job_id].cancel()
            del self.pubsub_tasks[job_id]


# Global connection manager
manager = ConnectionManager()


def verify_artisan_token(token: str, db: Session) -> User | None:
    """Verify JWT token and ensure user is an artisan."""
    try:
        payload = decode_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None

        if user.role != RoleEnum.artisan.value:
            return None

        return user
    except Exception:
        return None


def verify_client_token(token: str, db: Session) -> User | None:
    """Verify JWT token and ensure user is a client."""
    try:
        payload = decode_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None

        if user.role != RoleEnum.client.value:
            return None

        return user
    except Exception:
        return None


@router.websocket("/tracking/{job_id}")
async def tracking_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time geotracking.

    - Artisans connect with their token to send location updates
    - Clients connect with their token to receive location updates
    - Location updates are broadcast via Redis Pub/Sub to all listeners
    """
    # Extract token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    # Verify token and get user
    db = next(get_db())
    try:
        try:
            payload = decode_token(token)
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found or inactive")
            return

        user_role = user.role
    finally:
        db.close()

    # Validate job_id is a valid UUID
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        await websocket.close(code=4002, reason="Invalid job ID format")
        return

    # Verify the job (booking) exists
    db = next(get_db())
    try:
        booking = db.query(Booking).filter(Booking.id == job_uuid).first()
        if not booking:
            await websocket.close(code=4003, reason="Job not found")
            return
    finally:
        db.close()

    # Connect the websocket
    await manager.connect(websocket, job_id)

    # Start Pub/Sub listener for this job if not already running
    manager.ensure_pubsub_task(job_id)

    try:
        while True:
            # Receive location data
            data = await websocket.receive_text()
            try:
                location_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON format"}))
                continue

            # Validate required fields
            if "lat" not in location_data or "lng" not in location_data:
                await websocket.send_text(
                    json.dumps({"error": "Missing required fields: lat, lng"})
                )
                continue

            # If artisan, publish the location update
            if user_role == RoleEnum.artisan.value:
                # Add artisan ID and timestamp to the data
                location_data["artisan_id"] = int(user_id)
                location_data["job_id"] = job_id

                # Publish to Redis Pub/Sub
                await manager.publish_location(job_id, location_data)

                # Acknowledge receipt
                await websocket.send_text(
                    json.dumps({"status": "received", "job_id": job_id})
                )
            else:
                # Clients can only listen, not send location updates
                await websocket.send_text(
                    json.dumps({"error": "Only artisans can send location updates"})
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
        manager.cancel_pubsub_task(job_id)
    except Exception:
        manager.disconnect(websocket, job_id)
        manager.cancel_pubsub_task(job_id)
