from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import settings
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check(response: Response, db: Session = Depends(get_db)):
    """
    Health check endpoint to verify server, database, and Redis connectivity.

    Returns HTTP 200 when all dependencies are healthy, and HTTP 503 when any
    dependency is unavailable. Designed to be consumed by external uptime
    monitors (e.g. UptimeRobot) that trigger email/Slack alerts on failure.
    """
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check Redis connectivity
    try:
        if cache.redis is None:
            redis_status = "unhealthy"
        else:
            await cache.redis.ping()
            redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    overall_healthy = db_status == "healthy" and redis_status == "healthy"
    overall_status = "healthy" if overall_healthy else "unhealthy"

    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall_status,
        "project": settings.PROJECT_NAME,
        "database": db_status,
        "redis": redis_status,
        "debug": settings.DEBUG,
    }
