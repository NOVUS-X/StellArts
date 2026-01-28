import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings


class RedisClient:
    def __init__(self):
        self.redis: redis.Redis | None = None

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Test connection
        await self.redis.ping()

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.aclose()

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set a value in Redis with optional expiration"""
        if not self.redis:
            return False

        if isinstance(value, dict | list):
            value = json.dumps(value)

        await self.redis.set(key, value, ex=expire)
        return True

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis"""
        if not self.redis:
            return None

        value = await self.redis.get(key)
        if value is None:
            return None

        # Try to parse as JSON, return as string if it fails
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis"""
        if not self.redis:
            return False

        result = await self.redis.delete(key)
        return bool(result)

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self.redis:
            return False

        return bool(await self.redis.exists(key))


# Global Redis client instance
cache = RedisClient()
