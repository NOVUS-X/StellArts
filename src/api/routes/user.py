from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from src.schemas.nft import NFTCreate, NFTResponse

# 1. Define the router instead of trying to use 'app'
router = APIRouter()

# 2. Define a schema for documentation (Solves "document all endpoints")
class MintRequest(BaseModel):
    name: str = Field(..., examples=["StellArt #001"])
    description: str = Field(..., examples=["A unique digital collectible"])

# 3. Use @router instead of @app
@router.post("/mint", tags=["nfts"], summary="Mint a new NFT")
async def mint_nft(request: MintRequest):
    """
    Detailed documentation for the Swagger UI:
    - **name**: The name of the NFT to be created.
    - **description**: A short bio for the asset.
    """
    return {"status": "success", "asset": request.name}
