from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_client_or_artisan
from app.core.config import settings
from app.models.user import User
from app.schemas.materials import MaterialEstimateRequest, MaterialEstimateResponse
from app.services.bom_parser import merge_bom_inputs
from app.services.retail_materials import estimate_from_bom_lines

router = APIRouter(prefix="/materials")


@router.post("/estimate", response_model=MaterialEstimateResponse)
async def estimate_material_costs(
    body: MaterialEstimateRequest,
    _current_user: User = Depends(require_client_or_artisan),
):
    structured: list[tuple[float, str]] = []
    if body.line_items:
        structured = [(li.quantity, li.description) for li in body.line_items]
    lines = merge_bom_inputs(body.bom_text, structured or None)
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No BOM lines to price",
        )

    if not settings.RETAIL_PRODUCT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Material pricing API is not configured (RETAIL_PRODUCT_API_KEY)",
        )

    try:
        return await estimate_from_bom_lines(
            lines,
            settings=settings,
            zip_code=body.zip_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
