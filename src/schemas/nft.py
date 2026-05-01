from pydantic import BaseModel, Field
from typing import Optional

# This goes under src/schemas/nft.py
class NFTBase(BaseModel):
    name: str = Field(..., examples=["Galactic Explorer #001"])
    description: Optional[str] = Field(None, examples=["A rare digital artifact from the Stellar system."])

class NFTCreate(NFTBase):
    # Data required only during creation
    image_url: str = Field(..., examples=["https://ipfs.io/ipfs/Qm..."])

class NFTRead(NFTBase):
    # Data returned to the user (including the database ID)
    id: int
    owner_id: str = Field(..., examples=["GABC...123"])

    class Config:
        from_attributes = True # Allows Pydantic to read data from database models
