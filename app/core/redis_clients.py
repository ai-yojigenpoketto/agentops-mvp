import redis
import redis.asyncio as aioredis
from app.core.settings import settings

# Sync Redis client for RQ (must keep binary payloads intact)
sync_redis_client = redis.from_url(settings.redis_url, decode_responses=False)

# Async Redis client for SSE pub/sub (string responses are convenient)
async_redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


def get_sync_redis() -> redis.Redis:
    """Get sync Redis client."""
    return sync_redis_client


async def get_async_redis() -> aioredis.Redis:
    """Get async Redis client."""
    return async_redis_client
