from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import aiohttp

from app.core.config import Settings

logger = logging.getLogger(__name__)


def compute_scope_hash_bytes(markdown: str) -> bytes:
    normalized = markdown.replace("\r\n", "\n").rstrip() + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def compute_scope_hash_hex(markdown: str) -> str:
    return compute_scope_hash_bytes(markdown).hex()


async def _pin_pinata(jwt: str, markdown: str) -> dict[str, Any]:
    data = aiohttp.FormData()
    data.add_field(
        "file",
        markdown.encode("utf-8"),
        filename="sow.md",
        content_type="text/markdown; charset=utf-8",
    )
    data.add_field(
        "pinataMetadata",
        json.dumps({"name": "stellarts-sow"}),
        content_type="application/json",
    )
    headers = {"Authorization": f"Bearer {jwt}"}
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://api.pinata.cloud/pinning/pinFileToIPFS",
            data=data,
            headers=headers,
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                logger.warning("Pinata pin failed HTTP %s: %s", resp.status, text[:400])
                raise RuntimeError("Pinata upload failed")
            payload = json.loads(text)
            return payload


async def _pin_arweave_irys(
    base_url: str,
    token: str,
    markdown: str,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/tx/arweave"
    headers = {"Authorization": f"Bearer {token}"}
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url,
            data=markdown.encode("utf-8"),
            headers={**headers, "Content-Type": "text/markdown; charset=utf-8"},
        ) as resp:
            text = await resp.text()
            if resp.status not in (200, 201):
                logger.warning("Irys upload failed HTTP %s: %s", resp.status, text[:400])
                raise RuntimeError("Arweave/Irys upload failed")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"id": text.strip(), "raw": text}


async def pin_approved_sow(
    markdown: str,
    *,
    settings: Settings,
) -> dict[str, Any]:
    scope_hash_hex = compute_scope_hash_hex(markdown)
    scope_bytes = bytes.fromhex(scope_hash_hex)
    if len(scope_bytes) != 32 or scope_bytes == b"\x00" * 32:
        raise ValueError("Invalid scope hash")

    backend = (settings.SOW_STORAGE_BACKEND or "none").lower()
    result: dict[str, Any] = {
        "scope_hash_hex": scope_hash_hex,
        "storage_backend": backend,
        "ipfs_cid": None,
        "ipfs_uri": None,
        "arweave_id": None,
    }

    if backend == "pinata":
        if not settings.PINATA_JWT:
            raise ValueError("PINATA_JWT is not configured")
        pin = await _pin_pinata(settings.PINATA_JWT, markdown)
        cid = pin.get("IpfsHash") or pin.get("IpfsHash".lower())
        if not cid:
            raise RuntimeError("Pinata response missing IpfsHash")
        result["ipfs_cid"] = cid
        result["ipfs_uri"] = f"ipfs://{cid}"
        return result

    if backend in ("arweave", "irys", "arweave_irys"):
        if not settings.IRYS_NODE_URL or not settings.IRYS_API_TOKEN:
            raise ValueError("IRYS_NODE_URL and IRYS_API_TOKEN must be configured")
        body = await _pin_arweave_irys(
            settings.IRYS_NODE_URL,
            settings.IRYS_API_TOKEN,
            markdown,
        )
        tx_id = body.get("id") or body.get("data", {}).get("id")
        if not tx_id:
            raise RuntimeError("Irys response missing transaction id")
        result["arweave_id"] = str(tx_id)
        return result

    if backend == "none":
        return result

    raise ValueError(f"Unknown SOW_STORAGE_BACKEND: {backend}")
