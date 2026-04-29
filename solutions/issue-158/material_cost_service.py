"""
Issue #158 – Material Cost Index Integration

Connects to the Home Depot / Lowe's product APIs (or a mock when keys are
absent), parses a Bill-of-Materials list extracted from the SOW, maps items
to SKUs, and returns a summarised total estimated material cost.
"""

import os
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/materials", tags=["materials"])

# ---------------------------------------------------------------------------
# Config – set these env vars in production
# ---------------------------------------------------------------------------
HOME_DEPOT_API_KEY = os.getenv("HOME_DEPOT_API_KEY", "")
LOWES_API_KEY = os.getenv("LOWES_API_KEY", "")

HOME_DEPOT_SEARCH_URL = "https://api.homedepot.com/v2/products/search"
LOWES_SEARCH_URL = "https://api.lowes.com/v1/products"

# ---------------------------------------------------------------------------
# Fallback mock prices (used when no API key is configured)
# ---------------------------------------------------------------------------
MOCK_PRICES: dict[str, float] = {
    "pipe": 12.50,
    "wire": 8.75,
    "paint": 35.00,
    "lumber": 22.00,
    "drywall": 18.00,
    "tile": 45.00,
    "cement": 14.00,
    "screw": 6.00,
    "nail": 4.50,
    "insulation": 28.00,
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class BOMRequest(BaseModel):
    sow_text: str          # raw SOW markdown; BOM is extracted automatically
    zip_code: str          # used for local pricing where supported


class LineItem(BaseModel):
    description: str
    unit_price: float
    quantity: int
    subtotal: float


class MaterialCostResponse(BaseModel):
    line_items: list[LineItem]
    total_estimated_cost: float
    source: str            # "home_depot" | "lowes" | "mock"


# ---------------------------------------------------------------------------
# BOM extraction
# ---------------------------------------------------------------------------
_BOM_PATTERN = re.compile(r"^[-*]\s*(\d+)\s*[xX×]?\s*(\S[^\n\r]*)", re.MULTILINE)


def extract_bom(sow_text: str) -> list[tuple[int, str]]:
    """
    Extract (quantity, description) pairs from a SOW markdown.
    Looks for lines like:  - 3x copper pipe  or  * 2 sheets drywall
    """
    items = []
    for m in _BOM_PATTERN.finditer(sow_text):
        qty = int(m.group(1))
        # Strip optional trailing note after " - " or " – "
        desc = re.split(r"\s*[-–]\s", m.group(2))[0].strip().lower()
        items.append((qty, desc))
    return items


# ---------------------------------------------------------------------------
# Price lookup
# ---------------------------------------------------------------------------
async def _lookup_home_depot(description: str) -> Optional[float]:
    if not HOME_DEPOT_API_KEY:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            HOME_DEPOT_SEARCH_URL,
            params={"q": description, "apiKey": HOME_DEPOT_API_KEY},
        )
    if resp.status_code != 200:
        return None
    data = resp.json()
    products = data.get("products", [])
    if not products:
        return None
    return float(products[0].get("price", 0))


async def _lookup_lowes(description: str) -> Optional[float]:
    if not LOWES_API_KEY:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            LOWES_SEARCH_URL,
            params={"keyword": description, "apiKey": LOWES_API_KEY},
        )
    if resp.status_code != 200:
        return None
    data = resp.json()
    items = data.get("items", [])
    if not items:
        return None
    return float(items[0].get("regularPrice", 0))


def _mock_price(description: str) -> float:
    for keyword, price in MOCK_PRICES.items():
        if keyword in description:
            return price
    return 20.00  # generic fallback


async def get_unit_price(description: str) -> tuple[float, str]:
    """Return (price, source)."""
    price = await _lookup_home_depot(description)
    if price:
        return price, "home_depot"
    price = await _lookup_lowes(description)
    if price:
        return price, "lowes"
    return _mock_price(description), "mock"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/estimate", response_model=MaterialCostResponse)
async def estimate_material_cost(req: BOMRequest) -> MaterialCostResponse:
    """
    Parse the SOW for a Bill of Materials, look up real-time SKU prices,
    and return a summarised total estimated material cost.
    """
    bom = extract_bom(req.sow_text)
    if not bom:
        raise HTTPException(
            status_code=422,
            detail="No Bill of Materials found in SOW. "
                   "Add lines like '- 3x copper pipe' to the SOW.",
        )

    line_items: list[LineItem] = []
    sources: list[str] = []
    total = 0.0

    for qty, desc in bom:
        unit_price, source = await get_unit_price(desc)
        subtotal = round(unit_price * qty, 2)
        total += subtotal
        sources.append(source)
        line_items.append(
            LineItem(
                description=desc,
                unit_price=round(unit_price, 2),
                quantity=qty,
                subtotal=subtotal,
            )
        )

    # Prefer real API source label if any real call succeeded
    dominant_source = "mock"
    for s in sources:
        if s != "mock":
            dominant_source = s
            break

    return MaterialCostResponse(
        line_items=line_items,
        total_estimated_cost=round(total, 2),
        source=dominant_source,
    )
