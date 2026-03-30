from __future__ import annotations

import logging
import re
from typing import Any, Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.schemas.labor_pricing import (
    LaborPricingSuggestResponse,
    MatchedLaborJob,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)

ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

_JOB_ROWS: list[dict[str, Any]] | None = None


def clear_hydration() -> None:
    global _JOB_ROWS
    _JOB_ROWS = None


def extract_zip_from_location(location: str | None) -> str | None:
    if not location:
        return None
    m = ZIP_RE.search(location)
    return m.group(1) if m else None


def labor_reference_amount(booking: Booking) -> float | None:
    if booking.labor_cost is not None:
        v = float(booking.labor_cost)
        if v > 0:
            return v
    if booking.estimated_cost is not None:
        v = float(booking.estimated_cost)
        if v > 0:
            return v
    return None


def build_anonymized_job_rows(db: Session) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in (
        db.query(Booking).filter(Booking.status == BookingStatus.COMPLETED).all()
    ):
        labor = labor_reference_amount(b)
        if labor is None:
            continue
        svc = (b.service or "").strip()
        if len(svc) < 3:
            continue
        z = extract_zip_from_location(b.location)
        rows.append(
            {
                "anon_job_id": str(b.id),
                "zip": z,
                "service": svc,
                "labor": labor,
            }
        )
    return rows


def rehydrate_from_db(db: Session) -> tuple[int, int]:
    global _JOB_ROWS
    _JOB_ROWS = build_anonymized_job_rows(db)
    zips = {r.get("zip") for r in _JOB_ROWS if r.get("zip")}
    return len(_JOB_ROWS), len(zips)


def _get_rows(db: Session) -> list[dict[str, Any]]:
    global _JOB_ROWS
    if _JOB_ROWS is not None:
        return _JOB_ROWS
    return build_anonymized_job_rows(db)


def urgency_multiplier(level: UrgencyLevel) -> float:
    return {
        UrgencyLevel.low: 0.97,
        UrgencyLevel.normal: 1.0,
        UrgencyLevel.high: 1.12,
    }[level]


def rating_multiplier(rating: float | None) -> float:
    if rating is None:
        return 1.0
    m = 1.0 + 0.05 * (rating - 3.0)
    return float(max(0.92, min(1.12, m)))


def _select_pool(
    rows: list[dict[str, Any]],
    zip_code: str,
) -> tuple[list[dict[str, Any]], Literal["local", "expanded"]]:
    z = zip_code.strip()[:5]
    local = [r for r in rows if r.get("zip") == z]
    if local:
        return local, "local"
    if rows:
        return rows, "expanded"
    return [], "local"


def suggest_labor_price(
    db: Session,
    *,
    sow_text: str,
    zip_code: str,
    urgency: UrgencyLevel,
    artisan_average_rating: float | None,
    top_k: int = 5,
) -> LaborPricingSuggestResponse:
    rows = _get_rows(db)
    pool, scope = _select_pool(rows, zip_code)

    u_mul = urgency_multiplier(urgency)
    r_mul = rating_multiplier(artisan_average_rating)

    if not pool:
        return LaborPricingSuggestResponse(
            zip_code=zip_code.strip()[:5],
            region_scope=scope,
            matches_used=0,
            baseline_average_labor=None,
            urgency_multiplier=u_mul,
            rating_multiplier=r_mul,
            suggested_labor_price=None,
            matched_jobs=[],
        )

    docs = [r["service"] for r in pool]
    query = sow_text.strip()
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=4096,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.98,
    )
    try:
        mat = vectorizer.fit_transform(docs + [query])
    except ValueError as exc:
        logger.warning("TF-IDF fit failed: %s", exc)
        k = min(top_k, len(pool))
        picked = pool[:k]
        baseline = float(np.mean([p["labor"] for p in picked]))
        suggested = round(baseline * u_mul * r_mul, 2)
        return LaborPricingSuggestResponse(
            zip_code=zip_code.strip()[:5],
            region_scope=scope,
            matches_used=k,
            baseline_average_labor=round(baseline, 2),
            urgency_multiplier=u_mul,
            rating_multiplier=r_mul,
            suggested_labor_price=suggested,
            matched_jobs=[
                MatchedLaborJob(
                    anon_job_id=p["anon_job_id"],
                    similarity=0.0,
                    reference_labor_cost=p["labor"],
                )
                for p in picked
            ],
        )

    qv = mat[-1]
    doc_mat = mat[:-1]
    sims = cosine_similarity(qv, doc_mat).flatten()
    order = np.argsort(-sims)
    k = min(top_k, len(pool))
    top_idx = order[:k]
    picked = [pool[i] for i in top_idx]
    sim_vals = [float(sims[i]) for i in top_idx]

    baseline = float(np.mean([p["labor"] for p in picked]))
    suggested = round(baseline * u_mul * r_mul, 2)

    matched = [
        MatchedLaborJob(
            anon_job_id=p["anon_job_id"],
            similarity=round(s, 4),
            reference_labor_cost=p["labor"],
        )
        for p, s in zip(picked, sim_vals, strict=True)
    ]

    return LaborPricingSuggestResponse(
        zip_code=zip_code.strip()[:5],
        region_scope=scope,
        matches_used=len(picked),
        baseline_average_labor=round(baseline, 2),
        urgency_multiplier=u_mul,
        rating_multiplier=r_mul,
        suggested_labor_price=suggested,
        matched_jobs=matched,
    )
