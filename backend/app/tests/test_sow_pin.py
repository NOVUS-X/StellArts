from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services import sow_storage
from app.tests.test_crud_endpoints import get_auth_headers


def test_compute_scope_hash_stable():
    h1 = sow_storage.compute_scope_hash_hex("# Title\n\nBody\n")
    h2 = sow_storage.compute_scope_hash_hex("# Title\n\nBody\n")
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_pin_none_backend(monkeypatch):
    monkeypatch.setattr(settings, "SOW_STORAGE_BACKEND", "none")
    out = await sow_storage.pin_approved_sow("# SOW\n", settings=settings)
    assert out["storage_backend"] == "none"
    assert out["ipfs_cid"] is None
    assert len(out["scope_hash_hex"]) == 64


@pytest.mark.asyncio
async def test_pin_pinata_success(monkeypatch):
    monkeypatch.setattr(settings, "SOW_STORAGE_BACKEND", "pinata")
    monkeypatch.setattr(settings, "PINATA_JWT", "jwt")
    monkeypatch.setattr(
        sow_storage,
        "_pin_pinata",
        AsyncMock(return_value={"IpfsHash": "QmTest123"}),
    )

    out = await sow_storage.pin_approved_sow("# x\n", settings=settings)
    assert out["ipfs_cid"] == "QmTest123"
    assert out["ipfs_uri"] == "ipfs://QmTest123"


def test_sow_pin_endpoint_requires_auth(client):
    r = client.post(
        "api/v1/sow/pin",
        json={"markdown": "# hi", "approval_confirmed": True},
    )
    assert r.status_code == 403


def test_sow_pin_endpoint_ok(client, monkeypatch):
    async def fake_pin(md, *, settings):
        return {
            "scope_hash_hex": sow_storage.compute_scope_hash_hex(md),
            "storage_backend": "none",
            "ipfs_cid": None,
            "ipfs_uri": None,
            "arweave_id": None,
        }

    monkeypatch.setattr("app.api.v1.endpoints.sow.sow_storage.pin_approved_sow", fake_pin)

    headers = get_auth_headers(client, "sow_user@test.com", "Pass123!", "client")
    r = client.post(
        "api/v1/sow/pin",
        json={"markdown": "# Scope\n\nWork items.", "approval_confirmed": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["storage_backend"] == "none"
    assert len(data["scope_hash_hex"]) == 64
