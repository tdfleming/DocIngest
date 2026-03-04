"""Redis token bucket rate limiter for per-API-key rate limiting."""

import time
from dataclasses import dataclass
from urllib.parse import urlparse

import structlog
from redis.asyncio import Redis

from docingest.config import settings

log = structlog.get_logger()

_redis: Redis | None = None

# Lua script for atomic token bucket rate limiting.
# Uses a Redis hash with 'tokens' and 'last_refill' fields.
# Returns: [allowed (0/1), remaining (int), reset_seconds (int)]
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    -- First request: initialise bucket full
    tokens = limit
    last_refill = now
end

-- Refill: rate = limit tokens per 60 seconds
local elapsed = math.max(0, now - last_refill)
local refill_rate = limit / 60.0
tokens = math.min(limit, tokens + elapsed * refill_rate)
last_refill = now

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

local remaining = math.floor(tokens)

-- Reset seconds: time until bucket is full again
local deficit = limit - tokens
local reset_seconds = 0
if deficit > 0 and refill_rate > 0 then
    reset_seconds = math.ceil(deficit / refill_rate)
end

redis.call('HSET', key, 'tokens', tostring(tokens), 'last_refill', tostring(last_refill))
redis.call('EXPIRE', key, ttl)

return {allowed, remaining, reset_seconds}
"""


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset: int  # seconds until full bucket


async def init_rate_limiter() -> None:
    """Create the Redis connection for rate limiting."""
    global _redis
    if _redis is not None:
        return
    parsed = urlparse(settings.redis_url)
    host = parsed.hostname or "redis"
    port = parsed.port or 6379
    _redis = Redis(host=host, port=port, decode_responses=True)
    log.info("rate_limiter.init", host=host, port=port)


async def close_rate_limiter() -> None:
    """Close the rate limiter Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        log.info("rate_limiter.closed")


async def check_rate_limit(key_hash: str, limit: int) -> RateLimitResult:
    """Check and consume one token from the rate limit bucket.

    Args:
        key_hash: SHA-256 hash of the API key.
        limit: Maximum requests per minute for this key.

    Returns:
        RateLimitResult with allowed status and limit metadata.
    """
    if _redis is None:
        log.warning("rate_limiter.no_connection", action="fail_open")
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset=0)

    try:
        now = time.time()
        key = f"rate_limit:{key_hash}"
        ttl = 120  # 2x the 60s window

        result = await _redis.eval(
            _TOKEN_BUCKET_SCRIPT,
            1,
            key,
            str(limit),
            str(now),
            str(ttl),
        )

        allowed, remaining, reset_seconds = result
        return RateLimitResult(
            allowed=bool(allowed),
            limit=limit,
            remaining=int(remaining),
            reset=int(reset_seconds),
        )
    except Exception:
        log.warning("rate_limiter.error", action="fail_open", exc_info=True)
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset=0)
