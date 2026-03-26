"""
Embedding service for StellArts semantic search.

Responsibilities:
- Build a rich descriptive text for each artisan from their profile and on-chain stats.
- Generate OpenAI text-embedding-3-small embeddings (1536 dims).
- Cache embeddings in Redis to avoid redundant API calls.
"""
import json
import logging
from typing import Optional

import openai

from app.core.cache import cache
from app.core.config import settings
from app.models.artisan import Artisan

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
_ARTISAN_CACHE_TTL = 86_400  # 24 h; invalidate manually on profile update
_QUERY_CACHE_TTL = 3_600     # 1 h for query embeddings

_openai_client: Optional[openai.AsyncOpenAI] = None


def _get_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file to enable semantic search."
            )
        _openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ---------------------------------------------------------------------------
# Text enrichment
# ---------------------------------------------------------------------------

def build_artisan_text(
    artisan: Artisan,
    reputation_score: int = 0,
    total_jobs: int = 0,
) -> str:
    """
    Construct a single descriptive string that captures everything meaningful
    about an artisan for embedding purposes.

    Args:
        artisan: SQLAlchemy Artisan model instance.
        reputation_score: On-chain score scaled by 100 (e.g. 9250 = 92.5%).
                          Pass 0 when unavailable; the field is omitted from text.
        total_jobs: Total on-chain job count. Pass 0 when unavailable.
    """
    parts: list[str] = []

    if artisan.business_name:
        parts.append(f"Business: {artisan.business_name}")

    if artisan.description:
        parts.append(f"Description: {artisan.description}")

    if artisan.specialties:
        try:
            specialties = json.loads(artisan.specialties)
            if isinstance(specialties, list) and specialties:
                parts.append(f"Specialties: {', '.join(str(s) for s in specialties)}")
        except (json.JSONDecodeError, TypeError):
            parts.append(f"Specialties: {artisan.specialties}")

    if artisan.location:
        parts.append(f"Location: {artisan.location}")

    if artisan.experience_years:
        parts.append(f"Experience: {artisan.experience_years} years")

    if artisan.rating is not None:
        parts.append(
            f"Rating: {float(artisan.rating):.1f}/5 from {artisan.total_reviews} reviews"
        )

    # On-chain reputation stats (from Soroban contract via get_reputation_stats).
    # Integrate by passing artisan.user.stellar_address once that field is added.
    if total_jobs > 0:
        success_rate = reputation_score / 100.0
        parts.append(
            f"On-chain reputation: {success_rate:.1f}% success rate over {total_jobs} jobs"
        )

    return ". ".join(parts)


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

async def _call_openai(text: str) -> list[float]:
    """Raw call to the OpenAI embeddings API (no caching)."""
    client = _get_client()
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text.replace("\n", " "),
    )
    return response.data[0].embedding


async def get_query_embedding(query: str) -> list[float]:
    """
    Return the embedding for a search query string, using Redis as a short-lived
    cache so repeated identical queries don't burn API quota.
    """
    cache_key = f"embedding:query:{hash(query) & 0xFFFF_FFFF}"

    if cache.redis:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    embedding = await _call_openai(query)

    if cache.redis:
        await cache.set(cache_key, embedding, expire=_QUERY_CACHE_TTL)

    return embedding


async def generate_artisan_embedding(artisan: Artisan) -> list[float]:
    """
    Return (and cache) the embedding for a full artisan profile.

    On-chain stats are not fetched here because get_reputation_stats in
    soroban.py requires a source Keypair and currently returns a stub (0, 0).
    Pass reputation_score/total_jobs explicitly if you have them available.
    """
    cache_key = f"embedding:artisan:{artisan.id}"

    if cache.redis:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    text = build_artisan_text(artisan)
    embedding = await _call_openai(text)

    if cache.redis:
        await cache.set(cache_key, embedding, expire=_ARTISAN_CACHE_TTL)

    return embedding


async def invalidate_artisan_embedding(artisan_id: int) -> None:
    """
    Evict the cached embedding for an artisan.
    Call this whenever an artisan's profile is updated so stale vectors
    don't pollute future searches.
    """
    if cache.redis:
        await cache.delete(f"embedding:artisan:{artisan_id}")
