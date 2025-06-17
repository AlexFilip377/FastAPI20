import redis.asyncio as redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")

redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url("redis://redis:6379", decode_responses=True)
    return redis_client