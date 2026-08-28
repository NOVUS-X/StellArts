# Service exports for easy importing
from app.services.notification_service import (
    create_notification,
    dispatch_to_matched_artisans,
)


class NotificationService:
    @staticmethod
    def dispatch_smart_pitch(artisan, booking, pitch_message):
        return {
            "artisan_id": artisan.id,
            "booking_id": booking.id,
            "message": pitch_message,
            "status": "dispatched",
        }

    @staticmethod
    async def dispatch_to_matched_artisans(
        db, booking, latitude=None, longitude=None, limit=5
    ):
        return await dispatch_to_matched_artisans(
            db, booking, latitude, longitude, limit
        )

    @staticmethod
    def dispatch_push_notification(artisan_id: int, message: str):
        print(f"[PUSH NOTIFICATION] Artisan {artisan_id}: {message}")
        return {"artisan_id": artisan_id, "message": message, "status": "pushed"}


notification_service = NotificationService()

__all__ = [
    "NotificationService",
    "notification_service",
    "create_notification",
    "dispatch_to_matched_artisans",
]
