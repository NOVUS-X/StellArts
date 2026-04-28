"""Tests for issue-158 material cost service."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from material_cost_service import extract_bom, _mock_price


def test_extract_bom_basic():
    sow = "## Materials\n- 3x copper pipe\n- 2x drywall sheet\n"
    items = extract_bom(sow)
    assert len(items) == 2
    assert items[0] == (3, "copper pipe")
    assert items[1] == (2, "drywall sheet")


def test_extract_bom_empty():
    assert extract_bom("No materials listed here.") == []


def test_mock_price_known_keyword():
    assert _mock_price("copper pipe") == 12.50   # matches "pipe"
    assert _mock_price("interior paint") == 35.00  # matches "paint"


def test_mock_price_unknown_falls_back():
    assert _mock_price("widget xyz") == 20.00


@pytest.mark.asyncio
async def test_estimate_endpoint_mock():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from material_cost_service import router

    app = FastAPI()
    app.include_router(router)
    tc = TestClient(app)

    sow = "## SOW\n- 2x copper pipe\n- 1x interior paint\n"
    resp = tc.post("/materials/estimate", json={"sow_text": sow, "zip_code": "10001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "mock"
    # 2 * 12.50 + 1 * 35.00 = 60.00
    assert data["total_estimated_cost"] == pytest.approx(60.00)
    assert len(data["line_items"]) == 2
