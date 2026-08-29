import asyncio
import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from jose import JWTError
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.cache import cache
from app.core.security import decode_token
from app.core.websocket import manager
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import (
    ConversationOut,
    MessageOut,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/conversations", response_model=list[ConversationOut])
def get_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get a list of all conversations for the current user.
    """
    # Find all messages where user is sender or receiver
    # Note: Complex query for latest messages grouped by conversation can be simplified:
    conversations = {}
    messages = (
        db.query(Message)
        .filter(
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .order_by(desc(Message.created_at))
        .all()
    )

    for msg in messages:
        other_user_id = (
            msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        )
        if other_user_id not in conversations:
            other_user = db.query(User).filter(User.id == other_user_id).first()
            unread_count = (
                db.query(Message)
                .filter(
                    Message.sender_id == other_user_id,
                    Message.receiver_id == current_user.id,
                    Message.is_read.is_(False),
                )
                .count()
            )

            conversations[other_user_id] = {
                "other_user_id": other_user_id,
                "other_user_name": other_user.full_name or other_user.username,
                "other_user_avatar": other_user.avatar,
                "last_message": msg,
                "unread_count": unread_count,
            }

    return list(conversations.values())


@router.get("/history/{other_user_id}", response_model=list[MessageOut])
def get_chat_history(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """
    Get message history with a specific user.
    """
    messages = (
        db.query(Message)
        .filter(
            or_(
                and_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == other_user_id,
                ),
                and_(
                    Message.sender_id == other_user_id,
                    Message.receiver_id == current_user.id,
                ),
            )
        )
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return messages[::-1]  # Return chronologically


@router.post("/read/{other_user_id}")
def mark_messages_read(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Mark all messages from another user as read.
    """
    db.query(Message).filter(
        Message.sender_id == other_user_id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"status": "success"}


# WebSocket logic


async def listen_to_redis(user_id: int):
    """Listen to Redis channel for the user and forward to their active WebSockets."""
    if not cache.redis:
        return
    pubsub = cache.redis.pubsub()
    channel = f"chat:{user_id}"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.send_personal_message(data, user_id)
    except Exception as e:
        logger.error(f"Redis listen error for user {user_id}: {e}")
    finally:
        await pubsub.unsubscribe(channel)


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)
):
    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=1008)
        return

    if not payload:
        await websocket.close(code=1008)
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=1008)
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user.id)
    redis_task = asyncio.create_task(listen_to_redis(user.id))

    try:
        while True:
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            event_type = data.get("type")
            payload = data.get("data", {})

            if event_type == "chat_message":
                receiver_id = payload.get("receiver_id")
                content = payload.get("content")
                if receiver_id and content:
                    # Save to DB
                    msg = Message(
                        sender_id=user.id, receiver_id=receiver_id, content=content
                    )
                    db.add(msg)
                    db.commit()
                    db.refresh(msg)

                    # Convert to dict
                    msg_dict = {
                        "id": msg.id,
                        "sender_id": msg.sender_id,
                        "receiver_id": msg.receiver_id,
                        "content": msg.content,
                        "is_read": msg.is_read,
                        "created_at": msg.created_at.isoformat(),
                    }

                    event = {"type": "chat_message", "data": msg_dict}

                    # Publish to receiver's Redis channel
                    if cache.redis:
                        await cache.redis.publish(
                            f"chat:{receiver_id}", json.dumps(event)
                        )

                    # Also send back to sender
                    await manager.send_personal_message(event, user.id)

            elif event_type == "typing_indicator":
                receiver_id = payload.get("receiver_id")
                if receiver_id and cache.redis:
                    event = {
                        "type": "typing_indicator",
                        "data": {
                            "sender_id": user.id,
                            "is_typing": payload.get("is_typing", True),
                        },
                    }
                    await cache.redis.publish(f"chat:{receiver_id}", json.dumps(event))

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        redis_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user.id)
        redis_task.cancel()
