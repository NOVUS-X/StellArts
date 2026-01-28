from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    """Schema for creating a new booking"""
    artisan_id: int = Field(..., description="ID of the artisan to book")
    service: str = Field(..., min_length=1, description="Description of the service")
    date: datetime = Field(..., description="Scheduled date and time for the service")
    estimated_cost: float = Field(..., gt=0, description="Estimated cost of the service")
    estimated_hours: Optional[float] = Field(None, gt=0, description="Estimated hours for the job")
    location: Optional[str] = Field(None, max_length=500, description="Location for the service")
    notes: Optional[str] = Field(None, description="Additional notes")

    class Config:
        json_schema_extra = {
            "example": {
                "artisan_id": 1,
                "service": "Plumbing repair for kitchen sink",
                "date": "2026-02-15T10:00:00",
                "estimated_cost": 150.00,
                "estimated_hours": 2.5,
                "location": "123 Main St, Apt 4B",
                "notes": "Please bring replacement parts"
            }
        }


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""
    status: str = Field(..., description="New status for the booking")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "confirmed"
            }
        }


class BookingResponse(BaseModel):
    """Schema for booking response"""
    id: UUID
    client_id: int
    artisan_id: int
    service_description: str
    scheduled_date: Optional[datetime]
    estimated_cost: Optional[float]
    estimated_hours: Optional[float]
    status: str
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
