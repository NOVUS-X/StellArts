from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

import aiohttp

from app.core.config import settings

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "your",
    "have",
    "been",
    "were",
    "will",
    "shall",
    "must",
    "should",
    "replace",
    "install",
    "finish",
    "completed",
    "completion",
    "after",
    "photo",
    "photos",
    "work",
    "job",
    "project",
}

_MATERIALS = {
    "stone",
    "wood",
    "brick",
    "metal",
    "steel",
    "concrete",
    "tile",
    "glass",
    "ceramic",
    "marble",
    "granite",
    "plaster",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", value.lower())


def _extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize_text(text))
    return {token for token in tokens if len(token) > 2 and token not in _STOPWORDS}


def _extract_materials(text: str) -> set[str]:
    normalized = _normalize_text(text)
    return {material for material in _MATERIALS if material in normalized}


def _looks_like_media_reference(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:image/"))


def _build_local_analysis(sow: str, after_photos: Iterable[str]) -> dict[str, Any]:
    evidence_text = " ".join(after_photos)
    sow_keywords = _extract_keywords(sow)
    evidence_keywords = _extract_keywords(evidence_text)
    matched = sorted(sow_keywords & evidence_keywords)
    missing = sorted(sow_keywords - evidence_keywords)

    required_materials = _extract_materials(sow)
    evidence_materials = _extract_materials(evidence_text)
    unexpected_materials = sorted(evidence_materials - required_materials)

    fundamentally_wrong: list[str] = []
    if required_materials and unexpected_materials:
        fundamentally_wrong.append(
            "unexpected materials: " + ", ".join(unexpected_materials)
        )

    coverage = len(matched) / max(len(sow_keywords), 1)
    confidence = 0.15 + (0.7 * coverage)
    confidence -= min(0.3, 0.18 * len(missing))
    confidence -= min(0.4, 0.35 * len(fundamentally_wrong))
    confidence = max(0.0, min(1.0, round(confidence, 2)))

    if fundamentally_wrong:
        summary = (
            "The evidence conflicts with the SOW. "
            f"Missing deliverables: {', '.join(missing) if missing else 'none'}."
        )
    elif missing:
        summary = f"The evidence covers part of the SOW but is missing: {', '.join(missing)}."
    else:
        summary = "The evidence aligns with the stated scope of work."

    return {
        "completion_confidence": confidence,
        "verified": confidence >= settings.JOB_COMPLETION_ACCEPTANCE_THRESHOLD,
        "summary": summary,
        "matched_deliverables": matched,
        "missing_deliverables": missing,
        "fundamentally_wrong": fundamentally_wrong,
    }


def _photo_payload(photo: str) -> dict[str, Any]:
    if _looks_like_media_reference(photo):
        return {"type": "image_url", "image_url": {"url": photo}}
    return {"type": "text", "text": photo}


def _normalize_provider_result(payload: dict[str, Any], sow: str) -> dict[str, Any]:
    confidence = payload.get("completion_confidence", payload.get("confidence", 0.0))
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    confidence_value = max(0.0, min(1.0, confidence_value))

    matched = payload.get("matched_deliverables") or []
    missing = payload.get("missing_deliverables") or []
    wrong = payload.get("fundamentally_wrong") or payload.get("mismatches") or []
    summary = payload.get("summary") or payload.get("reason") or ""

    if not summary:
        if wrong:
            summary = "The vision model flagged a material mismatch against the SOW."
        elif missing:
            summary = "The vision model flagged missing deliverables against the SOW."
        else:
            summary = "The vision model found the work consistent with the SOW."

    return {
        "completion_confidence": round(confidence_value, 2),
        "verified": confidence_value >= settings.JOB_COMPLETION_ACCEPTANCE_THRESHOLD,
        "summary": summary,
        "matched_deliverables": list(matched),
        "missing_deliverables": list(missing),
        "fundamentally_wrong": list(wrong),
    }


async def _call_vision_model(
    *, scope_hash: str | None, sow: str, after_photos: list[str]
) -> dict[str, Any] | None:
    if not settings.VISION_API_URL:
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "You verify artisan job completion against the supplied scope of work. "
                "Return JSON with keys completion_confidence, summary, matched_deliverables, "
                "missing_deliverables, fundamentally_wrong. Use a 0.0 to 1.0 confidence score. "
                "Identify missing work or fundamentally wrong materials."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"ScopeHash: {scope_hash or 'n/a'}\n"
                        f"SOW: {sow}\n"
                        f"Photos: {len(after_photos)}"
                    ),
                },
                *[_photo_payload(photo) for photo in after_photos],
            ],
        },
    ]

    request_body = {
        "model": settings.VISION_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    headers = {"Content-Type": "application/json"}
    if settings.VISION_API_KEY:
        headers["Authorization"] = f"Bearer {settings.VISION_API_KEY}"

    timeout = aiohttp.ClientTimeout(total=60)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                settings.VISION_API_URL, json=request_body, headers=headers
            ) as response:
                if response.status >= 400:
                    return None
                payload = await response.json(content_type=None)
    except Exception:
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, str):
            parsed = json.loads(content)
        else:
            parsed = content
        if not isinstance(parsed, dict):
            return None
        return _normalize_provider_result(parsed, sow)
    except Exception:
        return None


async def assess_booking_completion(
    *, scope_hash: str | None, sow: str, after_photos: list[str]
) -> dict[str, Any]:
    """Assess completion quality using a vision model when available."""
    if not sow.strip() or not after_photos:
        return {
            "completion_confidence": 0.0,
            "verified": False,
            "summary": "A scope of work and at least one final photo are required.",
            "matched_deliverables": [],
            "missing_deliverables": _extract_keywords(sow) if sow else [],
            "fundamentally_wrong": [],
        }

    provider_result = await _call_vision_model(
        scope_hash=scope_hash, sow=sow, after_photos=after_photos
    )
    if provider_result is not None:
        return provider_result

    return _build_local_analysis(sow, after_photos)