# Service exports — use the real NotificationService
from app.services.notification_service import NotificationService, notification_service

__all__ = ["NotificationService", "notification_service"]
