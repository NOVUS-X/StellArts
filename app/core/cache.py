import aioredis
import json
from typing import Any, Optional
from app.core.config import settings

class RedisCache:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            
            if expire:
                return await self.redis.setex(key, expire, value)
            else:
                return await self.redis.set(key, value)
        except Exception as e:
            print(f"Redis SET error: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis"""
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Try to parse as JSON first
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            print(f"Redis GET error: {e}")
            return None
    
    async def set_session(self, session_id: str, data: dict, expire: int = 3600):
        """Set session data with expiration (default 1 hour)"""
        return await self.set(f"session:{session_id}", data, expire)
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data"""
        return await self.get(f"session:{session_id}")
    
    async def cache_geolocation(self, location_key: str, artisan_ids: list, expire: int = 300):
        """Cache artisan IDs for a geolocation query (default 5 minutes)"""
        return await self.set(f"geo:{location_key}", artisan_ids, expire)
    
    async def get_cached_geolocation(self, location_key: str) -> Optional[list]:
        """Get cached artisan IDs for a geolocation"""
        return await self.get(f"geo:{location_key}")

# Global cache instance
cache = RedisCache()
