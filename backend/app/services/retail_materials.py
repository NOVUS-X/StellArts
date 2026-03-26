from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from app.core.config import Settings
from app.schemas.materials import (
    MaterialEstimateResponse,
    MaterialLineEstimate,
)

logger = logging.getLogger(__name__)


async def fetch_bigbox_search(
    *,
    base_url: str,
    api_key: str,
    search_term: str,
    customer_zipcode: str | None,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    params: dict[str, str] = {
        "api_key": api_key,
        "type": "search",
        "search_term": search_term,
        "sort_by": "best_seller",
    }
    if customer_zipcode:
        params["customer_zipcode"] = customer_zipcode

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(base_url, params=params) as response:
            text = await response.text()
            if response.status != 200:
                logger.warning(
                    "Retail product API HTTP %s: %s",
                    response.status,
                    text[:500],
                )
                msg = "Retail product API returned an error"
                raise RuntimeError(msg)
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                logger.warning("Retail product API invalid JSON: %s", text[:200])
                raise RuntimeError("Retail product API returned invalid JSON") from exc


def _first_priced_hit(payload: dict[str, Any]) -> dict[str, Any] | None:
    info = payload.get("request_info") or {}
    if info.get("success") is False:
        return None
    for row in payload.get("search_results") or []:
        product = row.get("product") or {}
        offers = row.get("offers") or {}
        primary = offers.get("primary") or {}
        price = primary.get("price")
        sku = product.get("store_sku") or product.get("item_id")
        title = product.get("title")
        if price is None or not sku or not title:
            continue
        currency = primary.get("currency") or "USD"
        try:
            unit = float(price)
        except (TypeError, ValueError):
            continue
        return {
            "sku": str(sku),
            "title": str(title),
            "unit_price": unit,
            "currency": str(currency),
        }
    return None


async def estimate_from_bom_lines(
    lines: list[tuple[float, str]],
    *,
    settings: Settings,
    zip_code: str | None,
    fetch_search: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> MaterialEstimateResponse:
    if not settings.RETAIL_PRODUCT_API_KEY:
        raise ValueError("RETAIL_PRODUCT_API_KEY is not configured")

    search = fetch_search or fetch_bigbox_search

    merchant = settings.RETAIL_PRODUCT_MERCHANT_LABEL
    out_lines: list[MaterialLineEstimate] = []
    currency = "USD"
    total = 0.0

    for qty, description in lines:
        query = description.strip()
        payload = await search(
            base_url=settings.RETAIL_PRODUCT_API_BASE_URL,
            api_key=settings.RETAIL_PRODUCT_API_KEY,
            search_term=query,
            customer_zipcode=zip_code,
        )
        hit = _first_priced_hit(payload)
        if not hit:
            out_lines.append(
                MaterialLineEstimate(
                    description=description,
                    quantity=qty,
                    search_query=query,
                    status="unmatched",
                )
            )
            continue

        unit = hit["unit_price"]
        line_total = round(unit * qty, 2)
        total += line_total
        currency = hit["currency"] or currency
        out_lines.append(
            MaterialLineEstimate(
                description=description,
                quantity=qty,
                search_query=query,
                matched_title=hit["title"],
                sku=hit["sku"],
                unit_price=unit,
                line_total=line_total,
                currency=hit["currency"],
                status="matched",
            )
        )

    return MaterialEstimateResponse(
        lines=out_lines,
        total_estimated_cost=round(total, 2),
        currency=currency,
        merchant=merchant,
    )
