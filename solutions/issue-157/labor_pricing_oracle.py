"""
Issue #157 – RAG Labor Pricing Oracle

Builds a pricing engine that:
1. Stores anonymized completed-job records in a vector DB (ChromaDB in-process).
2. Given a SOW text, retrieves the ~5 most similar past jobs and averages
   their final labor costs.
3. Applies a modifier for urgency and artisan rating.
"""

import os
from typing import Optional

import chromadb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

router = APIRouter(prefix="/pricing", tags=["pricing"])

# ---------------------------------------------------------------------------
# Shared singletons (initialised once at import time)
# ---------------------------------------------------------------------------
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")
_chroma = chromadb.Client()
_collection = _chroma.get_or_create_collection("labor_jobs")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class JobRecord(BaseModel):
    job_id: str
    zip_code: str
    description: str
    final_labor_cost: float  # USD


class PriceQuery(BaseModel):
    sow_text: str
    zip_code: str
    urgency: str = "normal"   # "normal" | "urgent" | "emergency"
    artisan_rating: float = 4.0  # 1.0–5.0


class PriceEstimate(BaseModel):
    suggested_price: float
    base_average: float
    modifier: float
    matched_jobs: int


# ---------------------------------------------------------------------------
# Urgency / rating modifiers
# ---------------------------------------------------------------------------
URGENCY_MODIFIER = {"normal": 1.0, "urgent": 1.15, "emergency": 1.35}


def _rating_modifier(rating: float) -> float:
    """Higher-rated artisans command a small premium."""
    if rating >= 4.5:
        return 1.10
    if rating >= 4.0:
        return 1.05
    return 1.0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/jobs", status_code=201)
def ingest_job(job: JobRecord) -> dict:
    """
    Ingest a completed job into the vector DB.
    Call this after each escrow is Released to hydrate the pricing oracle.
    """
    embedding = _embed_model.encode(job.description).tolist()
    _collection.add(
        ids=[job.job_id],
        embeddings=[embedding],
        documents=[job.description],
        metadatas=[{"zip_code": job.zip_code, "cost": job.final_labor_cost}],
    )
    return {"status": "ingested", "job_id": job.job_id}


@router.post("/estimate", response_model=PriceEstimate)
def estimate_price(query: PriceQuery) -> PriceEstimate:
    """
    RAG-based labor price estimate.

    Embeds the SOW, queries the 5 nearest past jobs in the same zip code,
    averages their costs, then applies urgency + rating modifiers.
    """
    embedding = _embed_model.encode(query.sow_text).tolist()

    results = _collection.query(
        query_embeddings=[embedding],
        n_results=5,
        where={"zip_code": query.zip_code},
        include=["metadatas"],
    )

    metadatas = results.get("metadatas", [[]])[0]
    if not metadatas:
        raise HTTPException(
            status_code=404,
            detail="No historical jobs found for this zip code. Ingest some jobs first.",
        )

    costs = [m["cost"] for m in metadatas]
    base_avg = sum(costs) / len(costs)

    urgency_mod = URGENCY_MODIFIER.get(query.urgency, 1.0)
    rating_mod = _rating_modifier(query.artisan_rating)
    modifier = round(urgency_mod * rating_mod, 4)

    return PriceEstimate(
        suggested_price=round(base_avg * modifier, 2),
        base_average=round(base_avg, 2),
        modifier=modifier,
        matched_jobs=len(costs),
    )
