from pydantic import BaseModel, Field
router = APIRouter()

class Item(BaseModel):
    name: str = Field(examples=["Fubotoy"])
    price: float = Field(description="The price must be greater than zero", examples=[19.99])

@router.post("/items/", tags=["items"], summary="Create a new item")
async def create_item(item: Item):
    return {"message": "Item Created"}
    """
    Create an item with all the information:
    - **name**: each item must have a name
    - **price**: must be a float
    """
    return item
