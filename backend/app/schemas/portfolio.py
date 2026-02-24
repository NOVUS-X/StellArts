from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PortfolioItemCreate(BaseModel):
    image_url: str = Field(
        ..., max_length=500, description="URL of the portfolio image"
    )
    description: str | None = Field(
        None, description="Description of the portfolio item"
    )


class PortfolioItemUpdate(BaseModel):
    image_url: str | None = Field(
        None, max_length=500, description="URL of the portfolio image"
    )
    description: str | None = Field(
        None, description="Description of the portfolio item"
    )


class PortfolioItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artisan_id: int
    image_url: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class PortfolioResponse(BaseModel):
    artisan_id: int
    artisan_name: str
    portfolio_items: list[PortfolioItemOut]
