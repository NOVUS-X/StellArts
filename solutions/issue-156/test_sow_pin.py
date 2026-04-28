"""Tests for issue-156 SOW pin service (no real IPFS call)."""
import hashlib
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sow_pin_service import router, pin_to_ipfs

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_pin_sow_success(monkeypatch):
    async def mock_pin(booking_id, sow_markdown):
        return "QmFakeCid123"

    monkeypatch.setattr("sow_pin_service.pin_to_ipfs", mock_pin)

    resp = client.post("/sow/pin", json={
        "booking_id": "booking-1",
        "sow_markdown": "## SOW\n- 2x copper pipe"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ipfs_cid"] == "QmFakeCid123"
    expected_sha = hashlib.sha256("## SOW\n- 2x copper pipe".encode()).hexdigest()
    assert data["sha256"] == expected_sha


def test_pin_to_ipfs_raises_without_jwt():
    import asyncio
    import sow_pin_service
    original = sow_pin_service.PINATA_JWT
    sow_pin_service.PINATA_JWT = ""
    with pytest.raises(Exception):
        asyncio.get_event_loop().run_until_complete(
            pin_to_ipfs("b1", "some sow")
        )
    sow_pin_service.PINATA_JWT = original
