from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import search as search_endpoint
from app.core.cache import cache
from app.core.config import settings
from app.services import embedding as embedding_service


class _DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyDB:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, stmt):
        return _DummyResult(self.rows)


def _artisan(artisan_id: int, rating: float | None = None):
    return SimpleNamespace(
        id=artisan_id,
        business_name=f"Artisan {artisan_id}",
        description="Historic restoration specialist",
        specialties='["historic restoration"]',
        location="Old Town",
        rating=rating,
        total_reviews=12,
        is_available=True,
        is_verified=True,
    )


@pytest.mark.asyncio
async def test_semantic_search_requires_openai_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(cache, "redis", None)

    with pytest.raises(HTTPException) as exc:
        await search_endpoint.semantic_search(
            q="historic restoration",
            db=_DummyDB([]),
        )

    assert exc.value.status_code == 503
    assert "OPENAI_API_KEY" in exc.value.detail


@pytest.mark.asyncio
async def test_semantic_search_returns_cached_payload(monkeypatch):
    cached = {
        "query": "historic restoration",
        "results": [
            {
                "id": 7,
                "business_name": "Cached Artisan",
                "description": "already cached",
                "specialties": "[]",
                "location": "City",
                "rating": 4.5,
                "total_reviews": 3,
                "is_available": True,
                "is_verified": True,
                "semantic_similarity": 0.9,
                "reputation_weight": 0.8,
                "hybrid_score": 0.87,
            }
        ],
        "total": 1,
    }

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(cache, "redis", object())
    monkeypatch.setattr(cache, "get", AsyncMock(return_value=cached))
    monkeypatch.setattr(cache, "set", AsyncMock())

    embed_mock = AsyncMock()
    monkeypatch.setattr(search_endpoint, "get_query_embedding", embed_mock)

    response = await search_endpoint.semantic_search(
        q="historic restoration",
        db=_DummyDB([]),
    )

    assert response.total == 1
    assert response.results[0].id == 7
    embed_mock.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_hybrid_reranking(monkeypatch):
    # Lower semantic similarity but stronger reputation should win at low semantic weight.
    rows = [
        (_artisan(1, rating=1.0), 0.05),  # sim=0.95, rep=0.2
        (_artisan(2, rating=4.5), 0.20),  # sim=0.80, rep=0.9
    ]

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(cache, "redis", object())
    monkeypatch.setattr(cache, "get", AsyncMock(return_value=None))
    cache_set = AsyncMock()
    monkeypatch.setattr(cache, "set", cache_set)

    monkeypatch.setattr(
        search_endpoint,
        "get_query_embedding",
        AsyncMock(return_value=[0.1] * 1536),
    )

    response = await search_endpoint.semantic_search(
        q="historic restoration",
        limit=2,
        semantic_weight=0.3,
        db=_DummyDB(rows),
    )

    assert response.total == 2
    assert response.results[0].id == 2
    assert response.results[1].id == 1
    assert response.results[0].hybrid_score > response.results[1].hybrid_score
    cache_set.assert_called_once()


def test_build_artisan_text_includes_reputation_stats():
    artisan = SimpleNamespace(
        business_name="Stone & Lime Works",
        description="Conservation masonry",
        specialties='["historic restoration", "stone masonry"]',
        location="Lagos Island",
        experience_years=11,
        rating=4.8,
        total_reviews=31,
    )

    text = embedding_service.build_artisan_text(
        artisan=artisan,
        reputation_score=9250,
        total_jobs=20,
    )

    assert "Specialties: historic restoration, stone masonry" in text
    assert "On-chain reputation: 92.5% success rate over 20 jobs" in text


def test_build_artisan_text_falls_back_for_raw_specialties():
    artisan = SimpleNamespace(
        business_name="Woodline",
        description="Custom carpentry",
        specialties="woodwork",
        location="Abuja",
        experience_years=6,
        rating=4.2,
        total_reviews=14,
    )

    text = embedding_service.build_artisan_text(artisan=artisan)
    assert "Specialties: woodwork" in text
