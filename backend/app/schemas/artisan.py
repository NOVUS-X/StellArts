from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# Shared/Discovery Models
class ArtisanItem(BaseModel):
    id: int
    business_name: str | None = None
    description: str | None = None
    specialties: str | None = None
    experience_years: int | None = None
    hourly_rate: float | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_verified: bool = False
    is_available: bool = False
    rating: float | None = None
    total_reviews: int = 0
    distance_km: float | None = Field(
        None, description="Great-circle distance in kilometers"
    )


class PaginatedArtisans(BaseModel):
    items: list[ArtisanItem]
    total: int
    page: int
    page_size: int


# Creation/Update/Input Schemas
class ArtisanLocationUpdate(BaseModel):
    location: str | None = Field(
        None, max_length=200, description="Human-readable address"
    )
    latitude: Decimal | None = Field(
        None, ge=-90, le=90, description="Latitude coordinate"
    )
    longitude: Decimal | None = Field(
        None, ge=-180, le=180, description="Longitude coordinate"
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v):
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v):
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return v


class ArtisanProfileCreate(BaseModel):
    business_name: str | None = Field(None, max_length=200)
    description: str | None = None
    specialties: list[str] | None = Field(
        default_factory=list, description="List of specialties"
    )
    experience_years: int | None = Field(None, ge=0, le=50)
    hourly_rate: Decimal | None = Field(
        None, ge=0, description="Hourly rate in currency"
    )
    location: str | None = Field(
        None, max_length=200, description="Human-readable address"
    )
    latitude: Decimal | None = Field(
        None, ge=-90, le=90, description="Latitude coordinate"
    )
    longitude: Decimal | None = Field(
        None, ge=-180, le=180, description="Longitude coordinate"
    )

    @field_validator("specialties")
    @classmethod
    def validate_specialties(cls, v):
        if v and len(v) > 10:
            raise ValueError("Maximum 10 specialties allowed")
        return v


class ArtisanProfileUpdate(BaseModel):
    business_name: str | None = Field(None, max_length=200)
    description: str | None = None
    specialties: list[str] | None = Field(None, description="List of specialties")
    experience_years: int | None = Field(None, ge=0, le=50)
    hourly_rate: Decimal | None = Field(
        None, ge=0, description="Hourly rate in currency"
    )
    location: str | None = Field(
        None, max_length=200, description="Human-readable address"
    )
    latitude: Decimal | None = Field(
        None, ge=-90, le=90, description="Latitude coordinate"
    )
    longitude: Decimal | None = Field(
        None, ge=-180, le=180, description="Longitude coordinate"
    )
    is_available: bool | None = None


# Output Schema
class ArtisanOut(BaseModel):
    id: int
    user_id: int
    business_name: str | None = None
    description: str | None = None
    specialties: list[str] | None = None
    experience_years: int | None = None
    hourly_rate: Decimal | None = None
    location: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    is_verified: bool = False
    is_available: bool = True
    rating: Decimal | None = None
    total_reviews: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("specialties", mode="before")
    @classmethod
    def parse_specialties(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v


class ArtisanWithDistance(ArtisanOut):
    distance_km: float | None = Field(
        None, description="Distance in kilometers from search point"
    )


# Search & Filtering
class NearbyArtisansRequest(BaseModel):
    latitude: Decimal = Field(..., ge=-90, le=90, description="Search center latitude")
    longitude: Decimal = Field(
        ..., ge=-180, le=180, description="Search center longitude"
    )
    radius_km: float | None = Field(
        10.0, ge=0.1, le=100, description="Search radius in kilometers"
    )
    specialties: list[str] | None = Field(None, description="Filter by specialties")
    min_rating: float | None = Field(
        None, ge=0, le=5, description="Minimum rating filter"
    )
    is_available: bool | None = Field(True, description="Filter by availability")
    limit: int | None = Field(20, ge=1, le=100, description="Maximum number of results")


class NearbyArtisansResponse(BaseModel):
    artisans: list[ArtisanWithDistance]
    total_found: int
    search_center: dict = Field(description="Search center coordinates")
    radius_km: float


# Geolocation API
class GeolocationRequest(BaseModel):
    address: str = Field(
        ..., min_length=5, max_length=500, description="Address to geocode"
    )


class GeolocationResponse(BaseModel):
    latitude: Decimal
    longitude: Decimal
    formatted_address: str
    confidence: float | None = Field(None, description="Geocoding confidence score")


# Statistics
class ArtisanLocationStats(BaseModel):
    total_artisans: int
    artisans_with_location: int
    coverage_percentage: float
    top_locations: list[dict]
