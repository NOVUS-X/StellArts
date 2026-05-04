import time
import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import get_db
from app.services.soroban import soroban_server
from app.services.webhook_listener import WebhookListenerService, EventHandler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])
@router.get("/", response_model=dict, summary="Health check for all services")
async def health_check(
    db=Depends(get_db),
    redis_client: Redis = Depends(lambda: settings.REDIS_URL),
) -> dict:
    """
    Comprehensive health check endpoint.
    
    Returns the health status of:
    - Database connectivity
    - Redis connectivity
    - Soroban RPC server
    - Webhook listener service (if enabled)
    """
    checks = {
        "status": "healthy",
        "checks": {},
        "version": "1.0.0",
    }
    
    # Database health check
    try:
        result = await db.execute("SELECT 1")
        checks["database"] = {
            "status": "healthy",
            "details": "Database connection successful",
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        checks["status"] = "degraded"
    
    # Redis health check
    try:
        await redis_client.ping()
        checks["redis"] = {
            "status": "healthy",
            "details": "Redis connection successful",
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        checks["status"] = "degraded"
    
    # Soroban server health check
    try:
        network_passphrase = settings.SOROBAN_NETWORK_PASSPHRASE
        server_info = await soroban_server.server_info()
        checks["soroban"] = {
            "status": "healthy",
            "details": f"Connected to network: {server_info.network_passphrase}",
            "network_passphrase": network_passphrase,
        }
    except Exception as e:
        checks["soroban"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        checks["status"] = "degraded"
    
    # Webhook listener health check
    if settings.WEBHOOK_LISTENER_ENABLED:
        try:
            # Check Redis cursor storage capability
            test_key = f"webhook_listener:health_check:{int(time.time())}"
            await redis_client.setex(test_key, 60, "healthy")
            await redis_client.delete(test_key)
            
            checks["webhook_listener"] = {
                "status": "healthy",
                "enabled": True,
                "details": "Webhook listener is operational",
                "contract_address": settings.ESCROW_CONTRACT_ID or "not configured",
            }
        except Exception as e:
            checks["webhook_listener"] = {
                "status": "unhealthy",
                "error": str(e),
                "enabled": True,
            }
            checks["status"] = "degraded"
    else:
        checks["webhook_listener"] = {
            "status": "disabled",
            "enabled": False,
        }
    
    # Overall status determination
    unhealthy_count = sum(
        1 for check in checks["checks"].values() 
        if check["status"] == "unhealthy"
    )
    degraded_count = sum(
        1 for check in checks["checks"].values() 
        if check["status"] == "degraded"
    )
    
    if unhealthy_count > 0:
        checks["status"] = "unhealthy"
    elif degraded_count > 0:
        checks["status"] = "degraded"
    else:
        checks["status"] = "healthy"
    
    return {
        "status": checks["status"],
        "checks": checks["checks"],
        "timestamp": int(time.time()),
    }
