# Service exports for easy importing


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
    async def dispatch_to_matched_artisans(db, booking, limit=5):
        return []


notification_service = NotificationService()
