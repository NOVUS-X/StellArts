from fastapi import APIRouter

from app.api.v1.endpoints import admin, artisan, auth, booking, health, payments, stats, user

api_router = APIRouter()

# Include health endpoint
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(user.router, tags=["users"])
api_router.include_router(booking.router, tags=["bookings"])
api_router.include_router(artisan.router, tags=["artisans"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(stats.router, tags=["stats"])
