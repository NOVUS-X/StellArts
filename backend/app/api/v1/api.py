from fastapi import APIRouter

from app.api.v1.endpoints import admin
from app.api.v1.endpoints import artisan
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import booking
from app.api.v1.endpoints import health
from app.api.v1.endpoints import payments
from app.api.v1.endpoints import stats
from app.api.v1.endpoints import user

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(user.router, tags=["users"])
api_router.include_router(booking.router, tags=["bookings"])
api_router.include_router(artisan.router, tags=["artisans"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(stats.router, tags=["stats"])