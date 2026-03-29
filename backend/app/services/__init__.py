# Services module initialization
# Notification Service for StellArts

from sqlalchemy.orm import Session

from app.models.artisan import Artisan
from app.models.booking import Booking
from app.schemas.artisan import NearbyArtisansRequest
from app.services.artisan_service import find_nearby_artisans_cached


class NotificationService:
    """
    Service for dispatching smart pitches to matched artisans.
    """

    @staticmethod
    async def find_top_matched_artisans(
        db: Session, booking: Booking, limit: int = 5
    ) -> list[Artisan]:
        """
        Find top matched artisans based on service type and location.
        """
        service_keywords = []
        service_lower = booking.service.lower()
        specialties_map = {
            "plumbing": ["plumbing", "pipe", "leak", "drain", "water"],
            "electrical": ["electrical", "wire", "outlet", "switch", "circuit"],
            "painting": ["painting", "paint", "wall", "color", "coat"],
            "carpentry": ["carpentry", "wood", "furniture", "cabinet", "shelf"],
            "cleaning": ["cleaning", "clean", "maid", "janitorial", "wash"],
        }

        for specialty, keywords in specialties_map.items():
            if any(keyword in service_lower for keyword in keywords):
                service_keywords.append(specialty)

        if not service_keywords:
            service_keywords = ["general"]

        latitude = 40.7128  # Default to NYC coordinates
        longitude = -74.0060
        radius_km = 50

        request = NearbyArtisansRequest(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            specialties=service_keywords,
            min_rating=3.0,
            is_available=True,
            limit=limit,
        )

        result = await find_nearby_artisans_cached(db, request)
        return result.get("artisans", [])

    @staticmethod
    def dispatch_smart_pitch(
        artisan: Artisan, booking: Booking, pitch_message: str
    ) -> dict:
        """
        Dispatch smart pitch to an artisan.
        """
        notification_data = {
            "artisan_id": artisan.id,
            "artisan_name": f"{artisan.first_name} {artisan.last_name}",
            "booking_id": str(booking.id),
            "service": booking.service,
            "pitch_message": pitch_message,
            "estimated_cost": float(booking.estimated_cost),
            "location": booking.location,
            "status": "dispatched",
            "dispatch_timestamp": "2026-03-28T10:49:00Z",
        }

        print(f"📢 Dispatching smart pitch to artisan {artisan.id}: {pitch_message}")
        return notification_data

    @staticmethod
    async def dispatch_to_matched_artisans(
        db: Session, booking: Booking, limit: int = 5
    ) -> list[dict]:
        """
        Find top matched artisans and dispatch smart pitches to all of them.
        """
        matched_artisans = await NotificationService.find_top_matched_artisans(
            db, booking, limit
        )

        dispatch_results = []
        for artisan in matched_artisans:
            result = NotificationService.dispatch_smart_pitch(
                artisan, booking, booking.artisan_pitch
            )
            dispatch_results.append(result)

        return dispatch_results


notification_service = NotificationService()
