from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SOWPinRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=500_000)
    approval_confirmed: Literal[True] = Field(
        ...,
        description="Must be true: user explicitly approved this SOW text for pinning.",
    )


class SOWPinResponse(BaseModel):
    scope_hash_hex: str
    storage_backend: str
    ipfs_cid: str | None = None
    ipfs_uri: str | None = None
    arweave_id: str | None = None
