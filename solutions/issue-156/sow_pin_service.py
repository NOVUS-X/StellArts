"""
Issue #156 – SOW On-Chain Commitment: Backend IPFS pin service.

Uploads an approved SOW markdown to IPFS via the Pinata API and returns
the CID that must be passed to the escrow contract's `initialize` call.
"""

import hashlib
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sow", tags=["sow"])

PINATA_JWT = os.getenv("PINATA_JWT", "")
PINATA_PIN_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"


class SOWPinRequest(BaseModel):
    booking_id: str
    sow_markdown: str


class SOWPinResponse(BaseModel):
    ipfs_cid: str
    sha256: str  # local integrity check


async def pin_to_ipfs(booking_id: str, sow_markdown: str) -> str:
    """Upload SOW to IPFS via Pinata; return the CID."""
    if not PINATA_JWT:
        raise HTTPException(status_code=500, detail="PINATA_JWT not configured")

    payload = {
        "pinataContent": {"booking_id": booking_id, "sow": sow_markdown},
        "pinataMetadata": {"name": f"sow-{booking_id}"},
    }
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(PINATA_PIN_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"IPFS pin failed: {resp.text}")

    return resp.json()["IpfsHash"]


@router.post("/pin", response_model=SOWPinResponse)
async def pin_sow(req: SOWPinRequest) -> SOWPinResponse:
    """
    Pin an approved SOW to IPFS.

    Returns the IPFS CID to be stored in the escrow contract as `scope_hash`.
    """
    cid = await pin_to_ipfs(req.booking_id, req.sow_markdown)
    sha = hashlib.sha256(req.sow_markdown.encode()).hexdigest()
    return SOWPinResponse(ipfs_cid=cid, sha256=sha)
