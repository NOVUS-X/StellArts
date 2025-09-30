from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, user

api_router = APIRouter()

# Include health endpoint
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(user.router, tags=["users"])
