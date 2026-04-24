from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType
from app.schemas.notification import NotificationCreate
from typing import List
from uuid import UUID


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        reference_id: UUID | None = None,
    ) -> Notification:
        """Create a new notification for a user"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            reference_id=reference_id,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_user_notifications(
        db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[Notification]:
        """Get notifications for a user, ordered by creation date (newest first)"""
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_as_read(db: Session, notification_id: UUID, user_id: int) -> Notification | None:
        """Mark a specific notification as read"""
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notification:
            notification.read = True
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        """Mark all notifications for a user as read"""
        updated_count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read == False)
            .update({"read": True})
        )
        db.commit()
        return updated_count

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Get the count of unread notifications for a user"""
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read == False)
            .count()
        )

    @staticmethod
    def delete_notification(db: Session, notification_id: UUID, user_id: int) -> bool:
        """Delete a notification"""
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notification:
            db.delete(notification)
            db.commit()
            return True
        return False


notification_service = NotificationService()
