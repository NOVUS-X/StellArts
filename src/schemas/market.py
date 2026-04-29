# src/schemas/market.py
from pydantic import BaseModel, Field

class ListingResponse(BaseModel):
    id: str = Field(..., examples=["LIST-8829"])
    price: str = Field(..., examples=["50 XLM"])
    seller: str = Field(..., examples=["GABC...XYZ"])
    status: str = Field(..., examples=["active"])

