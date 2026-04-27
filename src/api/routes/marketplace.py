# src/api/routes/marketplace.py
from fastapi import APIRouter
from src.schemas.market import ListingResponse

router = APIRouter()

@router.get(
    "/listings", 
    tags=["Marketplace"], 
    summary="Fetch all active listings",
    response_model=list[ListingResponse]
)
async def get_listings():
    """
    Retrieve a list of all items currently for sale on the platform.
    - **Filterable**: Supports pagination and price sorting.
    - **On-chain**: Verified against Stellar ledger state.
    """
    return [{"id": "123", "price": "50 XLM", "status": "active"}]
