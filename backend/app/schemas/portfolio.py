from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class PortfolioItemCreate(BaseModel):
    image_url: str = Field(..., max_length=500, description="URL of the portfolio image")
    description: Optional[str] = Field(None, description="Description of the portfolio item")


class PortfolioItemUpdate(BaseModel):
    image_url: Optional[str] = Field(None, max_length=500, description="URL of the portfolio image")
    description: Optional[str] = Field(None, description="Description of the portfolio item")


class PortfolioItemOut(BaseModel):
    id: int
    artisan_id: int
    image_url: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PortfolioResponse(BaseModel):
    artisan_id: int
    artisan_name: str
    portfolio_items: List[PortfolioItemOut]
