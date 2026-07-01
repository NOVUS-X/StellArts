from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.services.notification_manager import manager


def create_notification(db: Session, notification: NotificationCreate) -> Notification:
    db_notification = Notification(
        user_id=notification.user_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        reference_id=notification.reference_id,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


async def send_notification_to_user(db: Session, notification: NotificationCreate):
    db_notification = create_notification(db, notification)
    await manager.send_notification(db_notification, notification.user_id)
    return db_notification


def get_user_notifications(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> List[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_notification(db: Session, notification_id: UUID, user_id: int) -> Optional[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )


def update_notification(
    db: Session, notification_id: UUID, user_id: int, update: NotificationUpdate
) -> Optional[Notification]:
    db_notification = get_notification(db, notification_id, user_id)
    if not db_notification:
        return None
    db_notification.is_read = update.is_read
    db.commit()
    db.refresh(db_notification)
    return db_notification


def mark_all_as_read(db: Session, user_id: int):
    db.query(Notification).filter(
        Notification.user_id == user_id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()


def delete_notification(db: Session, notification_id: UUID, user_id: int) -> bool:
    db_notification = get_notification(db, notification_id, user_id)
    if not db_notification:
        return False
    db.delete(db_notification)
    db.commit()
    return True


def get_unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )
