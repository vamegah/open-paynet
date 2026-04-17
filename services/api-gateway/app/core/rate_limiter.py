from functools import wraps

from fastapi import HTTPException
import redis.asyncio as redis

from .config import settings


redis_client = None


async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client

def rate_limit(requests: int, period: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            redis_client = await get_redis()
            user_id = kwargs.get("user_id", "anonymous")
            payment = kwargs.get("payment")
            if user_id == "anonymous" and payment is not None:
                user_id = getattr(payment, "user_id", "anonymous")

            key = f"rate-limit:{user_id}"
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, period)
            if current > requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
