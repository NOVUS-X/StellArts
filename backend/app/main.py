from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.cache import cache
from app.core.config import settings
from app.db.session import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await cache.initialize()  # Cambio: connect() -> initialize()
    yield
    # Shutdown
    await cache.close()  # Cambio: disconnect() -> close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        "health": f"{settings.API_V1_STR}/health"
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
            "message": "Redis is working correctly!"
        }
    except Exception as e:
        return {
            "redis_status": "error",
            "error": str(e)
        }

@app.get("/test-db")
async def test_database(db: Session = Depends(get_db)):
    """Test database connection"""
    try:
        # Test basic query (usar text() para SQL directo)
        result = db.execute(text("SELECT 1 as test"))
        test_value = result.fetchone()[0]

        return {
            "database_status": "connected",
            "test_query": test_value == 1,
            "message": "Database is working correctly!"
        }
    except Exception as e:
        return {
            "database_status": "error",
            "error": str(e)
        }
