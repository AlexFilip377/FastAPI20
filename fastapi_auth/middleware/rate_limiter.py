import redis.asyncio as redis
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi_auth.config import RATE_LIMIT


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str):
        super().__init__(app)
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        route = request.url.path
        key = f"rate:{client_ip}:{route}"
        
        current_time = int(time.time())
        window = current_time // RATE_LIMIT["window"]
        redis_key = f"{key}:{window}"
        
        count = await self.redis.incr(redis_key)
        if count == 1:
            await self.redis.expire(redis_key, RATE_LIMIT["window"])
            
        if count > RATE_LIMIT["limit"]:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."}
            )
        
        return await call_next(request)