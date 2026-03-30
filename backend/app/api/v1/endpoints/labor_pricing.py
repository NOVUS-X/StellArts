from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_admin, require_client_or_artisan
from app.db.session import get_db
from app.models.user import User
from app.schemas.labor_pricing import (
    LaborPricingReindexResponse,
    LaborPricingSuggestRequest,
    LaborPricingSuggestResponse,
)
from app.services import labor_pricing_engine

router = APIRouter(prefix="/pricing")


@router.post(
    "/labor/suggest",
    response_model=LaborPricingSuggestResponse,
)
def suggest_labor_pricing(
    body: LaborPricingSuggestRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_client_or_artisan),
):
    return labor_pricing_engine.suggest_labor_price(
        db,
        sow_text=body.sow_text,
        zip_code=body.zip_code,
        urgency=body.urgency,
        artisan_average_rating=body.artisan_average_rating,
    )


@router.post(
    "/labor/reindex",
    response_model=LaborPricingReindexResponse,
)
def reindex_labor_history(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    indexed, unique_zips = labor_pricing_engine.rehydrate_from_db(db)
    return LaborPricingReindexResponse(
        indexed_jobs=indexed,
        unique_zips=unique_zips,
    )
