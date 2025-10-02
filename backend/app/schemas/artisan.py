from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# Shared/Discovery Models
class ArtisanItem(BaseModel):
    id: int
    business_name: Optional[str] = None
    description: Optional[str] = None
    specialties: Optional[str] = None
    experience_years: Optional[int] = None
    hourly_rate: Optional[float] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_verified: bool = False
    is_available: bool = False
    rating: Optional[float] = None
    total_reviews: int = 0
    distance_km: Optional[float] = Field(None, description="Great-circle distance in kilometers")


class PaginatedArtisans(BaseModel):
    items: List[ArtisanItem]
    total: int
    page: int
    page_size: int


# Creation/Update/Input Schemas
class ArtisanLocationUpdate(BaseModel):
    location: Optional[str] = Field(None, max_length=200, description="Human-readable address")
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180, description="Longitude coordinate")

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if v is not None and (v < -90 or v > 90):
            raise ValueError('Latitude must be between -90 and 90 degrees')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if v is not None and (v < -180 or v > 180):
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return v


class ArtisanProfileCreate(BaseModel):
    business_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    specialties: Optional[List[str]] = Field(default_factory=list, description="List of specialties")
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate in currency")
    location: Optional[str] = Field(None, max_length=200, description="Human-readable address")
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180, description="Longitude coordinate")

    @field_validator('specialties')
    @classmethod
    def validate_specialties(cls, v):
        if v and len(v) > 10:
            raise ValueError('Maximum 10 specialties allowed')
        return v


class ArtisanProfileUpdate(BaseModel):
    business_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    specialties: Optional[List[str]] = Field(None, description="List of specialties")
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate in currency")
    location: Optional[str] = Field(None, max_length=200, description="Human-readable address")
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    is_available: Optional[bool] = None


# Output Schema
class ArtisanOut(BaseModel):
    id: int
    user_id: int
    business_name: Optional[str] = None
    description: Optional[str] = None
    specialties: Optional[List[str]] = None
    experience_years: Optional[int] = None
    hourly_rate: Optional[Decimal] = None
    location: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_verified: bool = False
    is_available: bool = True
    rating: Optional[Decimal] = None
    total_reviews: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtisanWithDistance(ArtisanOut):
    distance_km: Optional[float] = Field(None, description="Distance in kilometers from search point")


# Search & Filtering
class NearbyArtisansRequest(BaseModel):
    latitude: Decimal = Field(..., ge=-90, le=90, description="Search center latitude")
    longitude: Decimal = Field(..., ge=-180, le=180, description="Search center longitude")
    radius_km: Optional[float] = Field(10.0, ge=0.1, le=100, description="Search radius in kilometers")
    specialties: Optional[List[str]] = Field(None, description="Filter by specialties")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum rating filter")
    is_available: Optional[bool] = Field(True, description="Filter by availability")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Maximum number of results")


class NearbyArtisansResponse(BaseModel):
    artisans: List[ArtisanWithDistance]
    total_found: int
    search_center: dict = Field(description="Search center coordinates")
    radius_km: float


# Geolocation API
class GeolocationRequest(BaseModel):
    address: str = Field(..., min_length=5, max_length=500, description="Address to geocode")


class GeolocationResponse(BaseModel):
    latitude: Decimal
    longitude: Decimal
    formatted_address: str
    confidence: Optional[float] = Field(None, description="Geocoding confidence score")


# Statistics
class ArtisanLocationStats(BaseModel):
    total_artisans: int
    artisans_with_location: int
    coverage_percentage: float
    top_locations: List[dict]
