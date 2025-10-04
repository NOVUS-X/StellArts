# app/api/v1/endpoints/payments.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from decimal import Decimal
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.payments import hold_payment, release_payment, refund_payment

router = APIRouter()


class HoldRequest(BaseModel):
    client_secret: str
    booking_id: str
    amount: Decimal = Field(..., gt=0)


class ReleaseRequest(BaseModel):
    booking_id: str
    artisan_public: str
    amount: Decimal = Field(..., gt=0)


class RefundRequest(BaseModel):
    booking_id: str
    client_public: str
    amount: Decimal = Field(..., gt=0)


@router.post("/hold", summary="Hold funds into escrow for a booking")
def hold(req: HoldRequest, db: Session = Depends(get_db)):
    res = hold_payment(db, req.client_secret, req.booking_id, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/release", summary="Release escrow to artisan")
def release(req: ReleaseRequest, db: Session = Depends(get_db)):
    res = release_payment(db, req.booking_id, req.artisan_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/refund", summary="Refund escrow to client")
def refund(req: RefundRequest, db: Session = Depends(get_db)):
    res = refund_payment(db, req.booking_id, req.client_public, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
