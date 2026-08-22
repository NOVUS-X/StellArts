import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.i18n import get_locale_from_request
from app.core.limiter import limiter
from app.db.session import get_db
from app.workers.soroban_event_worker import run_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.initialize()
    task = asyncio.create_task(run_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await cache.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan,
)
app.state.limiter = limiter


def rate_limit_custom_handler(request: Request, exc: RateLimitExceeded):
    response = _rate_limit_exceeded_handler(request, exc)
    if "Retry-After" not in response.headers:
        # Fallback to ensure the header is always present as required by tests/clients
        response.headers["Retry-After"] = "60"
    return response


app.add_exception_handler(RateLimitExceeded, rate_limit_custom_handler)

# Ensure static/avatars directory exists
static_path = os.path.join(os.getcwd(), settings.STATIC_DIR)
avatars_path = os.path.join(static_path, settings.AVATARS_DIR)
if not os.path.exists(avatars_path):
    os.makedirs(avatars_path)

app.mount(f"/{settings.STATIC_DIR}", StaticFiles(directory=static_path), name="static")

# Register global exception handlers to ensure every error response follows
# the standardized { error_code, message, details } schema.
register_exception_handlers(app)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    """Resolve the client locale from Accept-Language and make it available
    on ``request.state.locale`` for downstream handlers.

    Also adds a ``Content-Language`` response header.
    """
    locale = get_locale_from_request(request)
    request.state.locale = locale
    response: Response = await call_next(request)
    response.headers["Content-Language"] = locale
    return response


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    """
    Root endpoint returning basic information about the API.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }


@app.get("/test-redis")
async def test_redis():
    """Test Redis connection and basic operations"""
    try:
        # Test SET
        await cache.set("test_key", "test_value", expire=60)

        # Test GET
        value = await cache.get("test_key")

        return {
            "redis_status": "connected",
            "set_get_test": value == "test_value",
            "test_value": value,
            "message": "Redis is working correctly!",
        }
    except Exception as e:
        return {"redis_status": "error", "error": str(e)}


@app.get("/test-db")
async def test_database(db: Session = Depends(get_db)):
    """Test database connection"""
    try:
        # Test basic query using raw SQL
        test_value = db.execute(text("SELECT 1 as test")).scalar()

        return {
            "database_status": "connected",
            "test_query": test_value == 1,
            "message": "Database is working correctly!",
        }
    except Exception as e:
        return {"database_status": "error", "error": str(e)}
