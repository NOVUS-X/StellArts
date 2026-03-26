from __future__ import annotations

import pytest

from app.services.bom_parser import merge_bom_inputs, parse_bom_text
from app.tests.test_crud_endpoints import get_auth_headers


def test_parse_bom_text_patterns():
    text = """2 - 2x4 lumber 8 ft
- 3 copper elbow 3/4 inch
Sheetrock (qty: 4)
10 drywall screws 1-1/4
# comment ignored
"""
    rows = parse_bom_text(text)
    assert rows == [
        (2.0, "2x4 lumber 8 ft"),
        (3.0, "copper elbow 3/4 inch"),
        (4.0, "Sheetrock"),
        (10.0, "drywall screws 1-1/4"),
    ]


def test_merge_bom_text_and_structured():
    merged = merge_bom_inputs(
        "1 - primer\n",
        [(2.0, "paint roller")],
    )
    assert merged[0] == (1.0, "primer")
    assert merged[1] == (2.0, "paint roller")


@pytest.mark.asyncio
async def test_estimate_aggregates_bigbox_payload(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RETAIL_PRODUCT_API_KEY", "test-key", raising=False)

    payload = {
        "request_info": {"success": True},
        "search_results": [
            {
                "product": {
                    "title": "Test 2x4",
                    "store_sku": "1001",
                    "item_id": "2002",
                },
                "offers": {"primary": {"price": 5.0, "currency": "USD"}},
            }
        ],
    }

    async def fake_fetch(**_kwargs):
        return payload

    from app.services import retail_materials

    result = await retail_materials.estimate_from_bom_lines(
        [(2.0, "2x4 stud"), (1.0, "2x4 stud")],
        settings=settings,
        zip_code="90210",
        fetch_search=fake_fetch,
    )
    assert result.currency == "USD"
    assert result.total_estimated_cost == 15.0
    assert len(result.lines) == 2
    assert all(line.status == "matched" for line in result.lines)
    assert result.lines[0].line_total == 10.0


def test_estimate_endpoint_requires_auth(client):
    resp = client.post(
        "api/v1/materials/estimate",
        json={"bom_text": "1 - nail", "line_items": None},
    )
    assert resp.status_code == 403


def test_estimate_endpoint_503_without_key(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RETAIL_PRODUCT_API_KEY", None, raising=False)
    headers = get_auth_headers(client, "mat@test.com", "Pass123!", "client")
    resp = client.post(
        "api/v1/materials/estimate",
        json={"bom_text": "1 - nail"},
        headers=headers,
    )
    assert resp.status_code == 503


def test_estimate_endpoint_happy_path(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RETAIL_PRODUCT_API_KEY", "k", raising=False)

    payload = {
        "request_info": {"success": True},
        "search_results": [
            {
                "product": {
                    "title": "Galvanized nail 5 lb",
                    "store_sku": "999",
                },
                "offers": {"primary": {"price": 12.5, "currency": "USD"}},
            }
        ],
    }

    async def fake_fetch(**_kwargs):
        return payload

    monkeypatch.setattr(
        "app.services.retail_materials.fetch_bigbox_search",
        fake_fetch,
    )

    headers = get_auth_headers(client, "mat2@test.com", "Pass123!", "artisan")
    resp = client.post(
        "api/v1/materials/estimate",
        json={"bom_text": "2 - box of nails", "zip_code": "90210"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_estimated_cost"] == 25.0
    assert data["lines"][0]["status"] == "matched"
