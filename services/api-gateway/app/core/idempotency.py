import json

import redis.asyncio as redis

from .config import settings


redis_client = None


async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client


async def get_cached_response(idempotency_key: str) -> dict | None:
    client = await get_redis()
    cached = await client.get(f"idempotency:{idempotency_key}")
    if not cached:
        return None
    return json.loads(cached)


async def cache_response(idempotency_key: str, response_payload: dict, ttl_seconds: int = 86400) -> None:
    client = await get_redis()
    await client.set(
        f"idempotency:{idempotency_key}",
        json.dumps(response_payload),
        ex=ttl_seconds,
    )
