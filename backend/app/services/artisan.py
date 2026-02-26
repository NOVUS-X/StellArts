from __future__ import annotations

import json

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.artisan import Artisan
from app.schemas.artisan import (
    ArtisanProfileCreate,
    ArtisanProfileUpdate,
    NearbyArtisansRequest,
)
from app.services.geolocation import geolocation_service


class ArtisanService:
    """Service for artisan operations with geolocation support"""

    def __init__(self, db: Session):
        self.db = db

    async def create_artisan_profile(
        self, user_id: int, profile_data: ArtisanProfileCreate
    ) -> Artisan | None:
        """Create artisan profile with geolocation support"""
        try:
            # Convert specialties list to JSON string
            specialties_json = (
                json.dumps(profile_data.specialties)
                if profile_data.specialties
                else None
            )

            artisan = Artisan(
                user_id=user_id,
                business_name=profile_data.business_name,
                description=profile_data.description,
                specialties=specialties_json,
                experience_years=profile_data.experience_years,
                hourly_rate=profile_data.hourly_rate,
                location=profile_data.location,
                latitude=profile_data.latitude,
                longitude=profile_data.longitude,
            )

            self.db.add(artisan)
            self.db.commit()
            self.db.refresh(artisan)

            # Add to Redis geospatial index if coordinates are provided
            if artisan.latitude and artisan.longitude:
                await geolocation_service.add_artisan_location(
                    artisan.id, artisan.latitude, artisan.longitude
                )

            return artisan
        except Exception as e:
            self.db.rollback()
            print(f"Error creating artisan profile: {e}")
            return None

    async def update_artisan_profile(
        self, artisan_id: int, profile_data: ArtisanProfileUpdate
    ) -> Artisan | None:
        """Update artisan profile with geolocation support"""
        try:
            artisan = self.db.query(Artisan).filter(Artisan.id == artisan_id).first()
            if not artisan:
                return None

            # Update fields if provided
            update_data = profile_data.model_dump(exclude_unset=True)

            # Handle specialties conversion
            if "specialties" in update_data and update_data["specialties"] is not None:
                update_data["specialties"] = json.dumps(update_data["specialties"])

            for field, value in update_data.items():
                setattr(artisan, field, value)

            self.db.commit()
            self.db.refresh(artisan)

            # Update Redis geospatial index if coordinates changed
            if artisan.latitude and artisan.longitude:
                await geolocation_service.add_artisan_location(
                    artisan.id, artisan.latitude, artisan.longitude
                )
            else:
                # Remove from index if coordinates were cleared
                await geolocation_service.remove_artisan_location(artisan.id)

            return artisan
        except Exception as e:
            self.db.rollback()
            print(f"Error updating artisan profile: {e}")
            return None

    def get_artisan_by_id(self, artisan_id: int) -> Artisan | None:
        """Get artisan by ID"""
        return self.db.query(Artisan).filter(Artisan.id == artisan_id).first()

    def get_artisan_by_user_id(self, user_id: int) -> Artisan | None:
        """Get artisan by user ID"""
        return self.db.query(Artisan).filter(Artisan.user_id == user_id).first()

    def list_artisans(
        self,
        skip: int = 0,
        limit: int = 100,
        specialties: list[str] | None = None,
        min_rating: float | None = None,
        is_available: bool | None = None,
        has_location: bool | None = None,
    ) -> list[Artisan]:
        """List artisans with optional filters"""
        query = self.db.query(Artisan)

        # Apply filters
        if specialties:
            # Filter by specialties (JSON contains any of the specified specialties)
            specialty_filters = []
            for specialty in specialties:
                specialty_filters.append(Artisan.specialties.contains(f'"{specialty}"'))
            query = query.filter(or_(*specialty_filters))

        if min_rating is not None:
            query = query.filter(Artisan.rating >= min_rating)

        if is_available is not None:
            query = query.filter(Artisan.is_available == is_available)

        if has_location is not None:
            if has_location:
                query = query.filter(
                    and_(Artisan.latitude.isnot(None), Artisan.longitude.isnot(None))
                )
            else:
                query = query.filter(
                    or_(Artisan.latitude.is_(None), Artisan.longitude.is_(None))
                )

        return query.offset(skip).limit(limit).all()

    async def find_nearby_artisans(self, request: NearbyArtisansRequest) -> dict:
        """Find nearby artisans using Redis geospatial queries"""
        try:
            # Get nearby artisan IDs from Redis
            nearby_data = await geolocation_service.find_nearby_artisans(
                request.latitude, request.longitude, request.radius_km, request.limit
            )

            if not nearby_data:
                return {
                    "artisans": [],
                    "total_found": 0,
                    "search_center": {
                        "latitude": float(request.latitude),
                        "longitude": float(request.longitude),
                    },
                    "radius_km": request.radius_km,
                }

            # Get artisan IDs
            artisan_ids = [item["artisan_id"] for item in nearby_data]

            # Query database for artisan details
            query = self.db.query(Artisan).filter(Artisan.id.in_(artisan_ids))

            # Apply additional filters
            if request.specialties:
                specialty_filters = []
                for specialty in request.specialties:
                    specialty_filters.append(
                        Artisan.specialties.contains(f'"{specialty}"')
                    )
                query = query.filter(or_(*specialty_filters))

            if request.min_rating is not None:
                query = query.filter(Artisan.rating >= request.min_rating)

            if request.is_available is not None:
                query = query.filter(Artisan.is_available == request.is_available)

            artisans = query.all()

            # Create distance mapping
            distance_map = {
                item["artisan_id"]: item["distance_km"] for item in nearby_data
            }

            # Convert to response format with distances
            artisan_results = []
            for artisan in artisans:
                artisan_dict = self._artisan_to_dict(artisan)
                artisan_dict["distance_km"] = distance_map.get(artisan.id, 0.0)
                artisan_results.append(artisan_dict)

            # Sort by distance
            artisan_results.sort(key=lambda x: x["distance_km"])

            return {
                "artisans": artisan_results,
                "total_found": len(artisan_results),
                "search_center": {
                    "latitude": float(request.latitude),
                    "longitude": float(request.longitude),
                },
                "radius_km": request.radius_km,
            }

        except Exception as e:
            print(f"Error finding nearby artisans: {e}")
            return {
                "artisans": [],
                "total_found": 0,
                "search_center": {
                    "latitude": float(request.latitude),
                    "longitude": float(request.longitude),
                },
                "radius_km": request.radius_km,
            }

    async def geocode_and_update_location(
        self, artisan_id: int, address: str
    ) -> Artisan | None:
        """Geocode address and update artisan location"""
        try:
            # Get coordinates from address
            geo_result = await geolocation_service.geocode_address(address)
            if not geo_result:
                return None

            # Update artisan with new coordinates
            artisan = self.db.query(Artisan).filter(Artisan.id == artisan_id).first()
            if not artisan:
                return None

            artisan.location = geo_result.formatted_address
            artisan.latitude = geo_result.latitude
            artisan.longitude = geo_result.longitude

            self.db.commit()
            self.db.refresh(artisan)

            # Update Redis index
            await geolocation_service.add_artisan_location(
                artisan.id, artisan.latitude, artisan.longitude
            )

            return artisan
        except Exception as e:
            self.db.rollback()
            print(f"Error geocoding and updating location: {e}")
            return None

    async def sync_locations_to_redis(self) -> int:
        """Sync all artisan locations from database to Redis"""
        try:
            # Get all artisans with coordinates
            artisans = (
                self.db.query(Artisan)
                .filter(
                    and_(Artisan.latitude.isnot(None), Artisan.longitude.isnot(None))
                )
                .all()
            )

            # Prepare bulk update data
            location_data = []
            for artisan in artisans:
                location_data.append(
                    {
                        "artisan_id": artisan.id,
                        "latitude": float(artisan.latitude),
                        "longitude": float(artisan.longitude),
                    }
                )

            # Bulk update Redis
            count = await geolocation_service.bulk_update_locations(location_data)
            return count
        except Exception as e:
            print(f"Error syncing locations to Redis: {e}")
            return 0

    def _artisan_to_dict(self, artisan: Artisan) -> dict:
        """Convert artisan model to dictionary with parsed specialties"""
        specialties = []
        if artisan.specialties:
            try:
                specialties = json.loads(artisan.specialties)
            except json.JSONDecodeError:
                specialties = []

        return {
            "id": artisan.id,
            "user_id": artisan.user_id,
            "business_name": artisan.business_name,
            "description": artisan.description,
            "specialties": specialties,
            "experience_years": artisan.experience_years,
            "hourly_rate": float(artisan.hourly_rate) if artisan.hourly_rate else None,
            "location": artisan.location,
            "latitude": float(artisan.latitude) if artisan.latitude else None,
            "longitude": float(artisan.longitude) if artisan.longitude else None,
            "is_verified": artisan.is_verified,
            "is_available": artisan.is_available,
            "rating": float(artisan.rating) if artisan.rating else None,
            "total_reviews": artisan.total_reviews,
            "created_at": artisan.created_at,
            "updated_at": artisan.updated_at,
        }

    def update_availability(self, artisan_id: int, is_available: bool) -> "Artisan | None":
        """Update artisan availability status"""
        try:
            artisan = self.db.query(Artisan).filter(Artisan.id == artisan_id).first()
            if not artisan:
                return None
            artisan.is_available = is_available
            self.db.commit()
            self.db.refresh(artisan)
            return artisan
        except Exception as e:
            self.db.rollback()
            print(f"Error updating artisan availability: {e}")
            return None

    async def delete_artisan(self, artisan_id: int) -> bool:
        """Delete artisan and remove from Redis index"""
        try:
            artisan = self.db.query(Artisan).filter(Artisan.id == artisan_id).first()
            if not artisan:
                return False

            # Remove from Redis first
            await geolocation_service.remove_artisan_location(artisan_id)

            # Delete from database
            self.db.delete(artisan)
            self.db.commit()

            return True
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting artisan: {e}")
            return False
