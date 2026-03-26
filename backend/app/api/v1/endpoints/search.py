"""
Semantic vector search endpoint for the StellArts artisan marketplace.

GET /search/semantic
  - Converts a natural-language query into an OpenAI embedding.
  - Performs a pgvector cosine-distance search against artisan embeddings.
  - Re-ranks results with a hybrid score:
      hybrid = semantic_weight * semantic_similarity
             + (1 - semantic_weight) * reputation_weight
    where reputation_weight = artisan.rating / 5.0
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import settings
from app.db.session import get_db
from app.models.artisan import Artisan
from app.services.embedding import get_query_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ArtisanSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_name: str | None
    description: str | None
    specialties: str | None   # raw JSON string; clients parse as needed
    location: str | None
    rating: float | None
    total_reviews: int
    is_available: bool
    is_verified: bool
    # Scores (higher is better, range 0-1)
    semantic_similarity: float
    reputation_weight: float
    hybrid_score: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[ArtisanSearchResult]
    total: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/semantic",
    response_model=SemanticSearchResponse,
    summary="Semantic artisan search",
    description=(
        "Find artisans using natural-language queries. "
        "Results are ranked by a hybrid of semantic similarity and on-chain "
        "reputation weight."
    ),
)
async def semantic_search(
    q: Annotated[str, Query(min_length=2, max_length=500, description="Natural-language search query")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    semantic_weight: Annotated[float, Query(ge=0.0, le=1.0, description="Weight for semantic similarity (0-1); remainder goes to reputation)")] = 0.7,
    available_only: Annotated[bool, Query(description="When true, only return artisans who are currently available")] = False,
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is not configured (OPENAI_API_KEY missing).",
        )

    # ------------------------------------------------------------------
    # 1. Check result cache (keyed on all search params)
    # ------------------------------------------------------------------
    cache_key = (
        f"search:semantic:{hash(q) & 0xFFFF_FFFF}"
        f":lim{limit}:sw{semantic_weight}:av{int(available_only)}"
    )
    if cache.redis:
        cached = await cache.get(cache_key)
        if cached is not None:
            return SemanticSearchResponse(**cached)

    # ------------------------------------------------------------------
    # 2. Embed the query
    # ------------------------------------------------------------------
    try:
        query_vector = await get_query_embedding(q)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # ------------------------------------------------------------------
    # 3. Cosine-distance search via pgvector (<=> operator)
    #    Fetch 3x the requested limit so re-ranking has enough candidates.
    # ------------------------------------------------------------------
    cosine_dist = Artisan.embedding.op("<=>")(query_vector)

    stmt = (
        select(Artisan, cosine_dist.label("cosine_distance"))
        .where(Artisan.embedding.isnot(None))
    )
    if available_only:
        stmt = stmt.where(Artisan.is_available.is_(True))

    stmt = stmt.order_by(cosine_dist).limit(limit * 3)

    rows = db.execute(stmt).all()

    if not rows:
        return SemanticSearchResponse(query=q, results=[], total=0)

    # ------------------------------------------------------------------
    # 4. Hybrid re-ranking
    #    semantic_similarity = 1 - cosine_distance  (OpenAI vecs are normalised)
    #    reputation_weight   = rating / 5.0
    #    hybrid_score        = w * sim + (1-w) * rep
    # ------------------------------------------------------------------
    reputation_weight_factor = 1.0 - semantic_weight
    scored: list[tuple[Artisan, float, float, float]] = []

    for artisan, cosine_distance in rows:
        semantic_sim = max(0.0, 1.0 - float(cosine_distance))
        rep = float(artisan.rating) / 5.0 if artisan.rating else 0.0
        hybrid = semantic_weight * semantic_sim + reputation_weight_factor * rep
        scored.append((artisan, semantic_sim, rep, hybrid))

    scored.sort(key=lambda t: t[3], reverse=True)
    top = scored[:limit]

    results = [
        ArtisanSearchResult(
            id=a.id,
            business_name=a.business_name,
            description=a.description,
            specialties=a.specialties,
            location=a.location,
            rating=float(a.rating) if a.rating is not None else None,
            total_reviews=a.total_reviews or 0,
            is_available=a.is_available,
            is_verified=a.is_verified,
            semantic_similarity=round(sim, 4),
            reputation_weight=round(rep, 4),
            hybrid_score=round(hybrid, 4),
        )
        for a, sim, rep, hybrid in top
    ]

    response = SemanticSearchResponse(query=q, results=results, total=len(results))

    # ------------------------------------------------------------------
    # 5. Cache the serialised response
    # ------------------------------------------------------------------
    if cache.redis:
        await cache.set(
            cache_key,
            response.model_dump(),
            expire=settings.SEMANTIC_CACHE_TTL,
        )

    return response
