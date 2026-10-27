"""Shared Redis connection for login lockout and auth rate limits."""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from clerk.config import Settings

logger = logging.getLogger("clerk.redis")


class RedisRequiredError(RuntimeError):
    """REDIS_REQUIRED is set and Redis did not answer the startup ping."""


async def connect_redis(settings: Settings) -> Redis | None:
    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        if settings.redis_required:
            logger.error("Redis required but unavailable (%s).", type(exc).__name__)
            raise RedisRequiredError(
                "Redis is required but did not answer the startup ping. "
                "Start Redis and check REDIS_URL."
            ) from exc
        logger.warning(
            "Redis unavailable (%s); auth rate limits and login lockout are off unless "
            "fail-closed settings block login.",
            type(exc).__name__,
        )
        return None
    logger.info("Redis answered the startup ping.")
    return client
