# app/api/v1/endpoints/payments.py
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.payments import (
    refund_payment,
    release_payment,
    prepare_payment,
    submit_signed_payment,
)

router = APIRouter()

# deprecated: used by the insecure /hold endpoint which has been removed





class PrepareRequest(BaseModel):
    booking_id: str
    amount: Decimal = Field(..., gt=0)
    client_public: str


class SubmitRequest(BaseModel):
    signed_xdr: str


class ReleaseRequest(BaseModel):
    booking_id: str
    artisan_public: str
    amount: Decimal = Field(..., gt=0)


class RefundRequest(BaseModel):
    booking_id: str
    client_public: str
    amount: Decimal = Field(..., gt=0)



# The old /hold endpoint has been removed due to security concerns. Clients
# should use the two-step prepare/submit flow instead.  A request to this path
# will now return 404 (FastAPI simply won't register it).



@router.post("/prepare", summary="Prepare unsigned payment XDR for client signing")
def prepare(req: PrepareRequest, db: Session = Depends(get_db)):
    # In a real app, booking ownership/authorization would be checked here
    return prepare_payment(req.booking_id, req.amount, req.client_public)


@router.post("/submit", summary="Submit signed payment XDR from wallet")
def submit(req: SubmitRequest, db: Session = Depends(get_db)):
    res = submit_signed_payment(db, req.signed_xdr)
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
