from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.core.auth import get_current_active_user, verify_access_token
from app.schemas.notification import (
    NotificationOut,
    UnreadCountOut,
    MarkAllAsReadOut,
    NotificationDeleteOut,
    NotificationUpdate,
)
from app.services import notification_service
from app.services.notification_manager import manager

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationOut])
def get_notifications(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return notification_service.get_user_notifications(
        db, current_user.id, skip=skip, limit=limit
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    count = notification_service.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read", response_model=NotificationOut)
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification = notification_service.update_notification(
        db, notification_id, current_user.id, NotificationUpdate(is_read=True)
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.put("/mark-all-read", response_model=MarkAllAsReadOut)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification_service.mark_all_as_read(db, current_user.id)
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}", response_model=NotificationDeleteOut)
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    success = notification_service.delete_notification(
        db, notification_id, current_user.id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted successfully"}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    # Authenticate the user using the token
    user = None
    try:
        payload = verify_access_token(token)
        user_id: int = payload.get("user_id")
        if user_id is None:
            await websocket.close(code=1008)
            return
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=1008)
            return
    except Exception as e:
        print(f"WebSocket auth error: {e}")
        await websocket.close(code=1008)
        return

    await manager.connect(user.id, websocket)
    try:
        while True:
            # Keep the connection alive by receiving messages (even if we don't use them)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user.id)
