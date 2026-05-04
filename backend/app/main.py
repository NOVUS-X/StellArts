import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
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
    lifespan=lifespan,
)

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
        "webhook_listener": f"{settings.API_V1_STR}/webhook/listener",
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
        # Test basic query (usar text() para SQL directo)
        result = db.execute(text("SELECT 1 as test"))
        test_value = result.fetchone()[0]

        return {
            "database_status": "connected",
            "test_query": test_value == 1,
            "message": "Database is working correctly!",
        }
    except Exception as e:
        return {"database_status": "error", "error": str(e)}
@app.post("/webhook/listener", summary="Webhook listener endpoint for Soroban events")
async def webhook_listener():
    """
    HTTP endpoint to receive webhook notifications from external systems.
    
    This endpoint allows external systems to notify about event updates
    that may need to be processed. The main event streaming should still
    use the SorobanServer.stream() in WebhookListenerService.
    """
    return {
        "status": "available",
        "message": "Webhook listener is operational",
        "note": "Main event streaming runs via SorobanServer.stream()",
    }
