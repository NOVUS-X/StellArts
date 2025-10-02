from typing import List, Optional
from pydantic import BaseModel, Field


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
