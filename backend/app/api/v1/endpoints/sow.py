from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_client_or_artisan
from app.core.config import settings
from app.models.user import User
from app.schemas.sow import SOWPinRequest, SOWPinResponse
from app.services import sow_storage

router = APIRouter(prefix="/sow")


@router.post("/pin", response_model=SOWPinResponse)
async def pin_scope_of_work(
    body: SOWPinRequest,
    _current_user: User = Depends(require_client_or_artisan),
):
    try:
        out = await sow_storage.pin_approved_sow(body.markdown, settings=settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return SOWPinResponse(**out)
